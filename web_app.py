"""
Flask + Socket.IO backend for event-driven Labyrinth Adventure.

This server does NOT capture stdout or use input(). Instead, it maintains a
GameEngine instance per Socket.IO client and relays structured JSON events
to the frontend. The frontend sends back actions to drive the engine.
"""

from flask import Flask, send_from_directory, request, jsonify, make_response
from flask_socketio import SocketIO, emit
from typing import Dict
import os
import uuid
from datetime import datetime

from pymongo import MongoClient, ASCENDING
from pymongo.errors import PyMongoError
from dotenv import load_dotenv

from game.engine import GameEngine

app = Flask(__name__, static_folder="static")

# Load environment variables from a local .env file if present (no effect in prod)
try:
    load_dotenv()
except Exception:
    pass

# Set a secret key for Flask (cookie signing, sessions). In this app we set our
# own device_id cookie, but providing SECRET_KEY is still good hygiene.
_secret_key = os.getenv("SECRET_KEY")
if _secret_key:
    try:
        app.secret_key = _secret_key
    except Exception:
        pass

# Configuration via environment variables for deployment flexibility
_cors_origins = os.getenv("CORS_ALLOWED_ORIGINS", "*")
_transports_env = os.getenv(
    "SOCKET_TRANSPORTS", "websocket,polling"
)  # e.g. "websocket,polling"
_transports = [t.strip() for t in _transports_env.split(",") if t.strip()]
_allow_upgrades = "websocket" in _transports or os.getenv(
    "ALLOW_UPGRADES", ""
).lower() in ("1", "true", "yes")
_message_queue = os.getenv("SOCKETIO_MESSAGE_QUEUE")  # e.g. redis URL for scale-out

# Let Flask-SocketIO auto-detect async mode by default (eventlet/gevent/threading)
_async_mode = os.getenv("SOCKETIO_ASYNC_MODE", "").strip() or None

socketio = SocketIO(
    app,
    async_mode=_async_mode,
    cors_allowed_origins=_cors_origins,
    logger=True,
    engineio_logger=True,
    transports=_transports or ["polling"],
    allow_upgrades=_allow_upgrades,
    message_queue=_message_queue,
)

# Keep engine instances per client session (sid)
engines: Dict[str, GameEngine] = {}


# ---- MongoDB setup ----
_mongo_client = None
_mongo_coll = None


def _get_mongo_collection():
    global _mongo_client, _mongo_coll
    if _mongo_coll is not None:
        return _mongo_coll
    # Env vars (support multiple common names)
    uri = os.getenv("MONGODB_URI") or os.getenv("MONGO_URI") or os.getenv("ATLAS_URI")
    if not uri:
        raise RuntimeError(
            "MongoDB URI not configured. Set MONGODB_URI (or MONGO_URI)."
        )
    db_name = os.getenv("MONGODB_DB") or os.getenv("MONGO_DB_NAME") or "labyrinth"
    coll_name = os.getenv("MONGODB_COLLECTION") or os.getenv(
        "MONGO_COLLECTION_NAME", "player_saves"
    )

    _mongo_client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    db = _mongo_client[db_name]
    _mongo_coll = db[coll_name]
    try:
        # Ensure unique index on device_id for upserts/overwrites per device
        _mongo_coll.create_index([("device_id", ASCENDING)], unique=True)
    except Exception:
        pass
    return _mongo_coll


def _get_device_id_from_request():
    # Prefer explicit header, then cookie
    did = request.headers.get("X-Device-ID") or request.args.get("device_id")
    if not did:
        try:
            did = request.cookies.get("device_id")
        except Exception:
            did = None
    return (did or "").strip()


@app.route("/")
def index():
    # Serve index; no-cache headers are applied in after_request
    resp = make_response(send_from_directory("static", "index.html"))
    # Ensure a stable device_id cookie without changing UI
    try:
        device_id = request.cookies.get("device_id")
    except Exception:
        device_id = None
    if not device_id:
        device_id = str(uuid.uuid4())
        # HttpOnly for security; SameSite=Lax is friendly for in-app REST calls
        # Secure only if running under HTTPS
        secure = os.getenv("FORCE_SECURE_COOKIES", "").lower() in ("1", "true", "yes")
        resp.set_cookie(
            "device_id",
            device_id,
            httponly=True,
            samesite="Lax",
            secure=secure,
            max_age=60 * 60 * 24 * 365 * 2,  # 2 years
        )
    return resp


@app.after_request
def add_no_cache_headers(resp):
    """Prevent aggressive caching of critical frontend assets to avoid stale UI.

    This targets index.html and the compiled app.js so updates are reflected
    immediately without requiring manual hard refresh.
    """
    try:
        p = request.path or ""
        if (
            p in ("/", "/index.html")
            or p.endswith("/index.html")
            or p == "/static/app.js"
        ):
            resp.headers["Cache-Control"] = (
                "no-store, no-cache, must-revalidate, max-age=0"
            )
            resp.headers["Pragma"] = "no-cache"
            resp.headers["Expires"] = "0"
    except Exception:
        pass
    return resp


@app.route("/health")
def health():
    """Lightweight health endpoint for Render health checks."""
    return jsonify({"ok": True}), 200


@app.route("/save-game", methods=["POST"])
def save_game():
    """Save a game state for a device. Overwrites existing by device_id.

    Expected JSON body: { "device_id": str (optional if cookie present), "game_state": {...} }
    """
    try:
        data = request.get_json(force=True, silent=False) or {}
    except Exception:
        return jsonify({"error": "Invalid JSON"}), 400

    device_id = (data.get("device_id") or _get_device_id_from_request() or "").strip()
    game_state = data.get("game_state")
    if not device_id:
        return (
            jsonify({"error": "device_id is required (header, cookie, or JSON)"}),
            400,
        )
    if not isinstance(game_state, dict):
        return jsonify({"error": "game_state must be an object"}), 400

    try:
        coll = _get_mongo_collection()
        doc = {
            "device_id": device_id,
            "game_state": game_state,
            "updated_at": datetime.utcnow(),
        }
        coll.update_one({"device_id": device_id}, {"$set": doc}, upsert=True)
        return jsonify({"ok": True}), 200
    except PyMongoError as e:
        return jsonify({"error": "Database error", "detail": str(e)}), 500


@app.route("/load-game", methods=["GET"])
def load_game():
    """Load a saved game state for a device.

    Accepts device_id via query string, header X-Device-ID, or device_id cookie.
    """
    device_id = _get_device_id_from_request()
    if not device_id:
        return (
            jsonify(
                {"error": "device_id is required (header, cookie, or query param)"}
            ),
            400,
        )
    try:
        coll = _get_mongo_collection()
        doc = coll.find_one({"device_id": device_id}, {"_id": 0})
        if not doc:
            return jsonify({"error": "No save found for this device"}), 404
        return (
            jsonify(
                {
                    "ok": True,
                    "device_id": device_id,
                    "game_state": doc.get("game_state", {}),
                }
            ),
            200,
        )
    except PyMongoError as e:
        return jsonify({"error": "Database error", "detail": str(e)}), 500


@app.route("/test-dragon")
def test_dragon():
    """Test route to demonstrate dragon background image"""
    return send_from_directory("static", "dragon_test.html")


@app.route("/simple-test")
def simple_test():
    """Simple test route without Socket.IO"""
    return send_from_directory("static", "simple_dragon_test.html")


@app.route("/direct-test")
def direct_test():
    """Direct Socket.IO test without React"""
    return send_from_directory("static", "direct_test.html")


def _emit_events(events, to_sid=None):
    """Emit engine events to frontend using consistent event names and payloads.
    Each emit includes: { type, text, options, state }.
    Additionally, message text is split into lines and sent as multiple game_output events
    to preserve CLI-like pacing.
    """
    # Latest state snapshot if provided in batch
    last_state = None
    for ev in events:
        etype = ev.get("type")
        # Track state event to attach in subsequent emits
        if etype == "state":
            last_state = ev.get("data", {})
            payload = {
                "type": "game_update",
                "text": "",
                "options": [],
                "state": last_state,
            }
            # Legacy/state update
            socketio.emit("game_update", payload, to=to_sid)
            # New explicit stats update
            socketio.emit("update_stats", payload, to=to_sid)
            continue

        if etype in ("message", "dialogue"):
            text = str(ev.get("text", ""))
            # split on newlines to emit line by line
            for line in text.splitlines():
                payload = {
                    "type": "game_output",
                    "text": line,
                    "options": [],
                    "state": last_state,
                }
                # Legacy dialogue/output
                socketio.emit("game_output", payload, to=to_sid)
                # New explicit dialogue channel
                socketio.emit("dialogue", {**payload, "type": "dialogue"}, to=to_sid)
            continue

        if etype == "pause":
            payload = {
                "type": "game_pause",
                "text": "[[PAUSE]]",
                "options": [],
                "state": last_state,
            }
            socketio.emit("game_pause", payload, to=to_sid)
            socketio.emit("pause", {**payload, "type": "pause"}, to=to_sid)
            continue

        if etype in ("choices", "menu"):
            items = ev.get("items", [])
            payload = {
                "type": "game_menu",
                "text": "",
                "options": items,
                "state": last_state,
            }
            socketio.emit("game_menu", payload, to=to_sid)
            socketio.emit("menu", {**payload, "type": "menu"}, to=to_sid)
            continue

        if etype == "combat_update":
            text = str(ev.get("text", ""))
            for line in text.splitlines():
                payload = {
                    "type": "combat_update",
                    "text": line,
                    "options": [],
                    "state": last_state,
                }
                socketio.emit("combat_update", payload, to=to_sid)
            continue

        if etype == "update_stats":
            payload = {
                "type": "update_stats",
                "text": "",
                "options": [],
                "state": ev.get("data", last_state),
            }
            socketio.emit("update_stats", payload, to=to_sid)
            continue

        if etype == "clear":
            socketio.emit("clear", {"type": "clear"}, to=to_sid)
            continue

        if etype == "scene":
            # Scene with background image and optional text
            data = ev.get("data", {})
            background = data.get("background")
            text = data.get("text", "")

            payload = {
                "type": "scene",
                "data": {"background": background, "text": text},
            }
            print(f"🎬 Emitting scene event: {payload}")
            socketio.emit("scene", payload, to=to_sid)
            continue

        if etype == "prompt":
            # represent prompt as an update with state, frontend shows input
            payload = {
                "type": "game_update",
                "text": ev.get("label", ""),
                "options": [],
                "state": last_state,
            }
            socketio.emit("game_update", payload, to=to_sid)
            # Also emit a dedicated prompt event for UI binding
            socketio.emit(
                "game_prompt",
                {
                    "type": "game_prompt",
                    "text": ev.get("label", ""),
                    "options": [],
                    "state": last_state,
                    "id": ev.get("id"),
                },
                to=to_sid,
            )
            continue

        # Fallback as update
        payload = {
            "type": "game_update",
            "text": str(ev),
            "options": [],
            "state": last_state,
        }
        socketio.emit("game_update", payload, to=to_sid)


@socketio.on("connect")
def on_connect():
    sid = request.sid
    # Create engine for this session
    eng = GameEngine()
    # Gate engine verbose prints via env var LE_ENGINE_DEBUG
    try:
        eng.debug = str(os.getenv("LE_ENGINE_DEBUG", "")).strip().lower() in (
            "1",
            "true",
            "yes",
        )
    except Exception:
        pass
    engines[sid] = eng
    emit("connected", {"ok": True})


@socketio.on("disconnect")
def on_disconnect():
    sid = request.sid
    engines.pop(sid, None)


@socketio.on("engine_start")
@socketio.on("player_start")
def on_engine_start():
    sid = request.sid

    # Set initial background to labyrinth.png for character creation
    from game.scene_manager import set_labyrinth_background

    initial_bg_event = set_labyrinth_background()
    _emit_events([initial_bg_event], to_sid=sid)

    eng = engines.get(sid)
    if not eng:
        eng = GameEngine()
        try:
            eng.debug = str(os.getenv("LE_ENGINE_DEBUG", "")).strip().lower() in (
                "1",
                "true",
                "yes",
            )
        except Exception:
            pass
        engines[sid] = eng
    events = eng.start()
    _emit_events(events, to_sid=sid)


@socketio.on("engine_action")
@socketio.on("player_action")
def on_engine_action(data):
    sid = request.sid
    eng = engines.get(sid)
    if not eng:
        return
    action = data.get("action") or ""
    payload = data.get("payload") or {}

    # Debug logging
    print(f"🎮 WEBAPP DEBUG: Received action={action}")
    print(
        f"🎮 WEBAPP DEBUG: Current engine phase={eng.s.phase}, subphase={eng.s.subphase}"
    )

    # Intercept web save to persist state without changing client UI
    if action == "town:save":
        try:
            device_id = _get_device_id_from_request()
            # If still missing, attempt from payload
            if not device_id:
                device_id = (payload.get("device_id") or "").strip()
            if not device_id:
                # Emit a gentle message and route back to town
                _emit_events(
                    [
                        {"type": "dialogue", "text": "Cannot save: missing device ID."},
                    ],
                    to_sid=sid,
                )
                events = eng.handle_action("town", {})
                _emit_events(events, to_sid=sid)
                return
            # Save current snapshot
            state = eng.snapshot()
            coll = _get_mongo_collection()
            doc = {
                "device_id": device_id,
                "game_state": state,
                "updated_at": datetime.utcnow(),
            }
            coll.update_one({"device_id": device_id}, {"$set": doc}, upsert=True)
            # Tell the user and gate with a Continue so the message is visible
            _emit_events(
                [
                    {"type": "dialogue", "text": "Game saved for this device."},
                    {"type": "pause"},
                    {"type": "menu", "items": [{"id": "town", "label": "Continue"}]},
                ],
                to_sid=sid,
            )
            return
        except Exception as e:
            _emit_events(
                [
                    {"type": "dialogue", "text": f"Save failed: {e}"},
                ],
                to_sid=sid,
            )
            events = eng.handle_action("town", {})
            _emit_events(events, to_sid=sid)
            return

    # Intercept main menu load to restore state from Mongo for this device
    if action == "main:load":
        try:
            device_id = _get_device_id_from_request()
            if not device_id:
                device_id = (payload.get("device_id") or "").strip()
            if not device_id:
                _emit_events(
                    [
                        {
                            "type": "dialogue",
                            "text": "Cannot load: missing device ID.",
                        }
                    ],
                    to_sid=sid,
                )
                # Re-render main menu
                events = eng.start()
                _emit_events(events, to_sid=sid)
                return
            coll = _get_mongo_collection()
            doc = coll.find_one({"device_id": device_id}, {"_id": 0})
            if not doc or not isinstance(doc.get("game_state"), dict):
                _emit_events(
                    [
                        {"type": "dialogue", "text": "No saved game found."},
                        {
                            "type": "menu",
                            "items": [
                                {"id": "main:new", "label": "New Game"},
                                {"id": "main:menu", "label": "Back"},
                            ],
                        },
                    ],
                    to_sid=sid,
                )
                return
            ok = False
            try:
                ok = bool(eng.load_snapshot(doc["game_state"]))
            except Exception:
                ok = False
            if not ok:
                _emit_events(
                    [
                        {
                            "type": "dialogue",
                            "text": "Failed to load save data.",
                        }
                    ],
                    to_sid=sid,
                )
                events = eng.start()
                _emit_events(events, to_sid=sid)
                return
            # On success, tell the player and show the appropriate screen (town)
            _emit_events(
                [
                    {"type": "dialogue", "text": "Loaded saved game."},
                ],
                to_sid=sid,
            )
            # Render town menu
            events = eng.handle_action("town", {})
            _emit_events(events, to_sid=sid)
            return
        except Exception as e:
            _emit_events(
                [
                    {"type": "dialogue", "text": f"Load failed: {e}"},
                ],
                to_sid=sid,
            )
            events = eng.start()
            _emit_events(events, to_sid=sid)
            return

    events = eng.handle_action(action, payload)

    print(
        f"🎮 WEBAPP DEBUG: After action, phase={eng.s.phase}, subphase={eng.s.subphase}"
    )
    print(f"🎮 WEBAPP DEBUG: Emitting {len(events)} events")

    _emit_events(events, to_sid=sid)


if __name__ == "__main__":
    if not os.path.exists("static"):
        os.makedirs("static", exist_ok=True)
    port = int(os.getenv("PORT", "5000"))
    host = os.getenv("HOST", "0.0.0.0")
    debug = os.getenv("FLASK_DEBUG", "").lower() in ("1", "true", "yes")
    print(f"🚀 Starting Flask-SocketIO server on {host}:{port} (debug={debug})...")
    socketio.run(app, host=host, port=port, debug=debug)
