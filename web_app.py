"""
Flask + Socket.IO backend for event-driven Labyrinth Adventure.

This server does NOT capture stdout or use input(). Instead, it maintains a
GameEngine instance per Socket.IO client and relays structured JSON events
to the frontend. The frontend sends back actions to drive the engine.
"""

# Runtime compatibility notes:
# - Python 3.13 + eventlet + TLS can trigger recursion in ssl.SSLContext.options
#   when PyMongo creates its SSL context. To avoid this in hosted environments
#   that might default to Python 3.13, we:
#   1) Avoid importing/monkey-patching eventlet by default.
#   2) Force Flask-SocketIO async_mode="threading" on Python >= 3.13.
#   3) Allow opting-in to eventlet via USE_EVENTLET=1 for older Python versions.
import sys
import os

_USE_EVENTLET = os.getenv("USE_EVENTLET", "").lower() in ("1", "true", "yes")
_IS_PY313_PLUS = sys.version_info >= (3, 13)

# Only consider eventlet when explicitly requested and when not on Python 3.13+
if _USE_EVENTLET and not _IS_PY313_PLUS:
    try:
        import eventlet  # type: ignore

        # Prevent SSL monkey-patch; PyMongo manages SSL context itself
        eventlet.monkey_patch(ssl=False)
    except Exception:
        pass

from flask import Flask, send_from_directory, request, jsonify, make_response
from flask_socketio import SocketIO, emit
from typing import Dict, Any
import uuid
from datetime import datetime
import json

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
_configured_transports = [
    t.strip()
    for t in os.getenv("SOCKET_TRANSPORTS", "websocket,polling").split(",")
    if t.strip()
]

# Force a safe async mode on Python 3.13+ to avoid eventlet/SSL recursion.
_forced_threading = _IS_PY313_PLUS or (
    os.getenv("FORCE_THREADING", "").lower() in ("1", "true", "yes")
)
_async_mode_env = os.getenv("SOCKETIO_ASYNC_MODE", "").strip().lower()
_async_mode = "threading" if _forced_threading else (_async_mode_env or None)

# When running in threading mode, prefer long-polling for maximum compatibility.
if _async_mode == "threading":
    _transports = ["polling"]
    _allow_upgrades = False
else:
    _transports = _configured_transports or ["polling"]
    _allow_upgrades = ("websocket" in _transports) or (
        os.getenv("ALLOW_UPGRADES", "").lower() in ("1", "true", "yes")
    )

_message_queue = os.getenv("SOCKETIO_MESSAGE_QUEUE")  # e.g. redis URL for scale-out

# Log the selected async mode and transports for easier diagnosis in prod
try:
    print(
        f"🔧 SocketIO config: async_mode={_async_mode or 'auto'} transports={_transports} allow_upgrades={_allow_upgrades}"
    )
    if _IS_PY313_PLUS:
        print("🔒 Python 3.13+ detected; using threading mode to avoid SSL recursion.")
except Exception:
    pass

socketio = SocketIO(
    app,
    async_mode=_async_mode,
    cors_allowed_origins=_cors_origins,
    logger=True,
    engineio_logger=True,
    transports=_transports,
    allow_upgrades=_allow_upgrades,
    message_queue=_message_queue,
)

# Keep engine instances per client session (sid)
engines: Dict[str, GameEngine] = {}
# Map Socket.IO session IDs to device IDs captured at connect time
sid_device: Dict[str, str] = {}


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


def _resolve_device_id(sid: str, payload: Dict = None) -> str:
    """Best-effort device_id resolution for Socket.IO events.

    Priority:
    1) Value captured at connect (sid_device)
    2) Explicit header/cookie on current request (when available)
    3) Payload-provided device_id
    """
    # 1) From connect-captured mapping
    try:
        did = sid_device.get(sid, "")
        if did:
            return did
    except Exception:
        pass
    # 2) From current request (handshake/polling may include cookies)
    try:
        did = _get_device_id_from_request()
        if did:
            # cache for future events
            sid_device[sid] = did
            return did
    except Exception:
        pass
    # 3) From payload (non-HttpOnly flows)
    try:
        if payload and isinstance(payload, dict):
            did = (payload.get("device_id") or "").strip()
            if did:
                sid_device[sid] = did
                return did
    except Exception:
        pass
    return ""


def _sanitize_for_bson(obj: Any, *, _depth: int = 0, _max: int = 8, _seen=None) -> Any:
    """Best-effort sanitizer to ensure data is BSON/JSON-serializable and acyclic.
    - Limits nesting depth
    - Converts unknown types to strings
    - Avoids cycles using an id() set
    """
    if _seen is None:
        _seen = set()
    try:
        oid = id(obj)
        if oid in _seen:
            return str(obj)
        _seen.add(oid)
    except Exception:
        pass

    if _depth > _max:
        return str(obj)

    # Primitives
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj

    # Datetime is BSON-compatible via PyMongo
    try:
        from datetime import datetime as _dt

        if isinstance(obj, _dt):
            return obj
    except Exception:
        pass

    # Dict-like
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            try:
                key = str(k)
            except Exception:
                key = repr(k)
            out[key] = _sanitize_for_bson(v, _depth=_depth + 1, _max=_max, _seen=_seen)
        return out

    # List/tuple
    if isinstance(obj, (list, tuple)):
        return [
            _sanitize_for_bson(x, _depth=_depth + 1, _max=_max, _seen=_seen)
            for x in obj
        ]

    # Fallback to string
    try:
        return json.loads(json.dumps(obj, default=str))
    except Exception:
        try:
            return str(obj)
        except Exception:
            return None


def _safe_weapon(w: Any) -> Dict[str, Any]:
    try:
        return {
            "name": str(getattr(w, "name", "")),
            "damage_die": str(getattr(w, "damage_die", "")),
            "damaged": bool(getattr(w, "damaged", False)),
        }
    except Exception:
        return {"name": "", "damage_die": "", "damaged": False}


def _safe_armor(a: Any) -> Dict[str, Any]:
    try:
        return {
            "name": str(getattr(a, "name", "")),
            "armor_class": int(getattr(a, "armor_class", 0)),
            "damaged": bool(getattr(a, "damaged", False)),
        }
    except Exception:
        return {"name": "", "armor_class": 0, "damaged": False}


def _safe_magic_item(mi: Any) -> Dict[str, Any]:
    try:
        return {
            "name": str(getattr(mi, "name", "")),
            "type": str(getattr(mi, "type", "")),
            "effect": str(getattr(mi, "effect", "")),
            "cursed": bool(getattr(mi, "cursed", False)),
            "description": str(getattr(mi, "description", "")),
            "bonus": int(getattr(mi, "bonus", 0)),
            "penalty": int(getattr(mi, "penalty", 0)),
            "damage_die": str(getattr(mi, "damage_die", "")),
            "bonus_damage": str(getattr(mi, "bonus_damage", "")),
        }
    except Exception:
        return {
            "name": "",
            "type": "",
            "effect": "",
            "cursed": False,
            "description": "",
            "bonus": 0,
            "penalty": 0,
            "damage_die": "",
            "bonus_damage": "",
        }


def _safe_companion(cp: Any) -> Dict[str, Any]:
    try:
        return {
            "name": str(getattr(cp, "name", "")),
            "species": str(getattr(cp, "species", "")),
            "hp": int(getattr(cp, "hp", 0)),
            "max_hp": int(getattr(cp, "max_hp", 0)),
            "armor_class": int(getattr(cp, "armor_class", 0)),
            "damage_die": str(getattr(cp, "damage_die", "")),
            "strength": int(getattr(cp, "strength", 0)),
        }
    except Exception:
        return {
            "name": "",
            "species": "",
            "hp": 0,
            "max_hp": 0,
            "armor_class": 0,
            "damage_die": "",
            "strength": 0,
        }


def _safe_character(c: Any) -> Dict[str, Any]:
    try:
        weapons = []
        try:
            for w in list(getattr(c, "weapons", []) or []):
                weapons.append(_safe_weapon(w))
        except Exception:
            pass
        armors_owned = []
        try:
            for a in list(getattr(c, "armors_owned", []) or []):
                armors_owned.append(_safe_armor(a))
        except Exception:
            pass
        magic_items = []
        try:
            for mi in list(getattr(c, "magic_items", []) or []):
                magic_items.append(_safe_magic_item(mi))
        except Exception:
            pass
        comp = None
        try:
            _cp = getattr(c, "companion", None)
            if _cp is not None:
                comp = _safe_companion(_cp)
        except Exception:
            comp = None
        side_q = []
        try:
            for q in list(getattr(c, "side_quests", []) or []):
                if isinstance(q, dict):
                    side_q.append({str(k): q[k] for k in q.keys()})
                else:
                    side_q.append(str(q))
        except Exception:
            pass
        return {
            "name": str(getattr(c, "name", "Adventurer")),
            "clazz": str(getattr(c, "clazz", "Adventurer")),
            "max_hp": int(getattr(c, "max_hp", 1)),
            "gold": int(getattr(c, "gold", 0)),
            "hp": int(getattr(c, "hp", 0)),
            "weapons": weapons,
            "armor": (
                _safe_armor(getattr(c, "armor")) if getattr(c, "armor", None) else None
            ),
            "attributes": dict(getattr(c, "attributes", {})),
            "potions": int(getattr(c, "potions", 0)),
            "potion_uses": dict(getattr(c, "potion_uses", {})),
            "spells": dict(getattr(c, "spells", {})),
            "trained_times": int(getattr(c, "trained_times", 0)),
            "persistent_buffs": dict(getattr(c, "persistent_buffs", {})),
            "companion": comp,
            "xp": int(getattr(c, "xp", 0)),
            "magic_items": magic_items,
            "equipped_weapon_index": int(getattr(c, "equipped_weapon_index", -1)),
            "armors_owned": armors_owned,
            "level": int(getattr(c, "level", 1)),
            "rest_attempted": bool(getattr(c, "rest_attempted", False)),
            "prayed": bool(getattr(c, "prayed", False)),
            "side_quests": side_q,
            "death_count": int(getattr(c, "death_count", 0)),
            "examine_used_this_turn": bool(getattr(c, "examine_used_this_turn", False)),
            "attribute_training": dict(getattr(c, "attribute_training", {})),
        }
    except Exception:
        return {
            "name": "Adventurer",
            "clazz": "Adventurer",
            "max_hp": 1,
            "gold": 0,
            "hp": 0,
            "weapons": [],
            "armor": None,
            "attributes": {},
            "potions": 0,
            "potion_uses": {},
            "spells": {},
            "trained_times": 0,
            "persistent_buffs": {},
            "companion": None,
            "xp": 0,
            "magic_items": [],
            "equipped_weapon_index": -1,
            "armors_owned": [],
            "level": 1,
            "rest_attempted": False,
            "prayed": False,
            "side_quests": [],
            "death_count": 0,
            "examine_used_this_turn": False,
            "attribute_training": {},
        }


def _safe_snapshot(eng: GameEngine) -> Dict[str, Any]:
    """Return a robust minimal snapshot, avoiding dataclasses.asdict recursion."""
    try:
        # Try the engine's snapshot first (fast path)
        return eng.snapshot()
    except Exception:
        pass
    # Manual fallback
    try:
        phase = str(getattr(getattr(eng, "s", None), "phase", "town"))
        depth = int(getattr(getattr(eng, "s", None), "depth", 1))
        ch = getattr(getattr(eng, "s", None), "character", None)
        return {
            "phase": phase,
            "depth": depth,
            "character": _safe_character(ch) if ch else None,
        }
    except Exception:
        return {"phase": "town", "depth": 1, "character": None}


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


@app.route("/health/db")
def health_db():
    """Optional health endpoint to verify Mongo connectivity in deployments."""
    try:
        coll = _get_mongo_collection()
        # quick roundtrip without creating or reading large docs
        coll.estimated_document_count()  # may use metadata
        return jsonify({"ok": True}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


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
    # Capture device_id from the handshake cookies if present
    try:
        did = _get_device_id_from_request()
        if did:
            sid_device[sid] = did
    except Exception:
        pass
    emit("connected", {"ok": True})


@socketio.on("disconnect")
def on_disconnect():
    sid = request.sid
    engines.pop(sid, None)
    sid_device.pop(sid, None)


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
            device_id = _resolve_device_id(sid, payload)
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
            # Save current snapshot; detect whether we are overwriting an existing save
            try:
                state = eng.snapshot()
            except Exception:
                # Fallback to a manual safe snapshot to avoid recursion
                state = _safe_snapshot(eng)
            # Best-effort sanitize to prevent recursion/non-serializable types in prod
            safe_state = _sanitize_for_bson(state)
            # Quick validation: ensure JSON serializable (avoids surprising BSON failures)
            try:
                json.dumps(safe_state, default=str)
            except Exception:
                # Fallback to a minimal shape if needed
                try:
                    ch = state.get("character") if isinstance(state, dict) else None
                except Exception:
                    ch = None
                safe_state = {
                    "depth": (
                        int(state.get("depth", 1)) if isinstance(state, dict) else 1
                    ),
                    "character": {
                        "name": (
                            (ch or {}).get("name") if isinstance(ch, dict) else None
                        ),
                        "clazz": (
                            (ch or {}).get("clazz") if isinstance(ch, dict) else None
                        ),
                        "hp": (
                            int((ch or {}).get("hp", 0)) if isinstance(ch, dict) else 0
                        ),
                        "max_hp": (
                            int((ch or {}).get("max_hp", 0))
                            if isinstance(ch, dict)
                            else 0
                        ),
                        "gold": (
                            int((ch or {}).get("gold", 0))
                            if isinstance(ch, dict)
                            else 0
                        ),
                        "level": (
                            int((ch or {}).get("level", 1))
                            if isinstance(ch, dict)
                            else 1
                        ),
                        "attributes": (
                            dict((ch or {}).get("attributes", {}))
                            if isinstance(ch, dict)
                            else {}
                        ),
                    },
                }
            coll = _get_mongo_collection()
            doc = {
                "device_id": device_id,
                "game_state": safe_state,
                "updated_at": datetime.utcnow(),
            }
            # Check existence first to craft message
            existed = bool(coll.find_one({"device_id": device_id}, {"_id": 1}))
            coll.update_one({"device_id": device_id}, {"$set": doc}, upsert=True)
            # Tell the user and gate with a Continue so the message is visible
            msg = (
                "Overwrote previous save for this device."
                if existed
                else "Game saved for this device."
            )
            try:
                print(
                    f"💾 SAVE OK device_id={device_id} existed={existed} depth={safe_state.get('depth')} char={(safe_state.get('character') or {}).get('name')}"
                )
            except Exception:
                pass
            _emit_events(
                [
                    {"type": "dialogue", "text": msg},
                    {"type": "pause"},
                    {"type": "menu", "items": [{"id": "town", "label": "Continue"}]},
                ],
                to_sid=sid,
            )
            return
        except Exception as e:
            # Print full traceback to help diagnose recursion source on Render
            try:
                import traceback as _tb

                print("💥 SAVE TRACE:\n" + _tb.format_exc())
            except Exception:
                pass
            try:
                print(
                    f"💥 SAVE ERROR device_id={device_id if 'device_id' in locals() else None}: {e}"
                )
            except Exception:
                pass
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
            device_id = _resolve_device_id(sid, payload)
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
            # Sanitize the loaded snapshot to avoid unexpected/cyclic data
            raw = doc.get("game_state", {})
            safe: Dict[str, any] = {}
            try:
                safe["depth"] = int(raw.get("depth", 1))
            except Exception:
                safe["depth"] = 1
            ch = raw.get("character")
            if isinstance(ch, dict):
                # Whitelist allowed character fields only
                allowed_keys = {
                    "name",
                    "clazz",
                    "max_hp",
                    "gold",
                    "hp",
                    "weapons",
                    "armor",
                    "attributes",
                    "potions",
                    "potion_uses",
                    "spells",
                    "trained_times",
                    "persistent_buffs",
                    "companion",
                    "xp",
                    "magic_items",
                    "equipped_weapon_index",
                    "armors_owned",
                    "level",
                    "rest_attempted",
                    "prayed",
                    "side_quests",
                    "death_count",
                    "examine_used_this_turn",
                    "attribute_training",
                }
                safe["character"] = {k: v for k, v in ch.items() if k in allowed_keys}
            else:
                safe["character"] = None

            ok = False
            try:
                ok = bool(eng.load_snapshot(safe))
            except Exception as _e:
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
            # On success, tell the player and gate with a Continue so message is visible
            try:
                print(
                    f"📥 LOAD OK device_id={device_id} depth={safe.get('depth')} char={(safe.get('character') or {}).get('name')}"
                )
            except Exception:
                pass
            _emit_events(
                [
                    {"type": "dialogue", "text": "Loaded saved game."},
                    {"type": "pause"},
                    {"type": "menu", "items": [{"id": "town", "label": "Continue"}]},
                ],
                to_sid=sid,
            )
            # Do not immediately render town; wait for client to click Continue (id: 'town')
            return
        except Exception as e:
            try:
                print(
                    f"💥 LOAD ERROR device_id={device_id if 'device_id' in locals() else None}: {e}"
                )
            except Exception:
                pass
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
