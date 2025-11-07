"""
Flask + Socket.IO backend for event-driven Labyrinth Adventure.

This server does NOT capture stdout or use input(). Instead, it maintains a
GameEngine instance per Socket.IO client and relays structured JSON events
to the frontend. The frontend sends back actions to drive the engine.
"""

# Avoid importing eventlet to prevent unintended monkey patching attempts on Python 3.13.

from flask import Flask, send_from_directory, request, jsonify, make_response
import socketio
from socketio import ASGIApp
from asgiref.wsgi import WsgiToAsgi  # type: ignore
from typing import Dict
import os
import uuid
from datetime import datetime

from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import PyMongoError
import certifi
from http.cookies import SimpleCookie
from bson import ObjectId

from game.engine import GameEngine
from game.reviews import submit_review, ReviewError

app = Flask(__name__, static_folder="static")

# Configuration via environment variables for deployment flexibility
_cors_origins = os.getenv("CORS_ALLOWED_ORIGINS", "*")
# Enforce WebSocket transport per requirements; no polling fallback
_transports = ["websocket"]
_allow_upgrades = True
_message_queue = os.getenv("SOCKETIO_MESSAGE_QUEUE")  # e.g. redis URL for scale-out

# Native ASGI Socket.IO server (no monkey patching)
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=_cors_origins,
    logger=True,
    engineio_logger=True,
    transports=_transports,
    allow_upgrades=_allow_upgrades,
    message_queue=_message_queue,
)

# Combined ASGI app: Socket.IO + Flask (wrapped for ASGI)
asgi_app = ASGIApp(sio, other_asgi_app=WsgiToAsgi(app))

# Keep engine instances per client session (sid)
engines: Dict[str, GameEngine] = {}
# Track device_id per sid for Socket.IO connections
sid_device: Dict[str, str] = {}


# ---- MongoDB setup ----
_mongo_client = None
_mongo_coll = None
_mongo_lb = None


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

    # Initialize the global MongoClient once using certifi's CA bundle for TLS
    if _mongo_client is None:
        _mongo_client = MongoClient(
            uri,
            serverSelectionTimeoutMS=5000,
            tlsCAFile=certifi.where(),
        )
    db = _mongo_client[db_name]
    _mongo_coll = db[coll_name]
    try:
        # Ensure unique index on device_id for upserts/overwrites per device
        _mongo_coll.create_index([("device_id", ASCENDING)], unique=True)
    except Exception:
        pass
    return _mongo_coll


def _get_leaderboard_collection():
    """Get or create the leaderboard collection for winners."""
    global _mongo_lb
    if _mongo_lb is not None:
        return _mongo_lb
    coll = _get_mongo_collection()
    db = coll.database
    coll_name = os.getenv("MONGODB_LEADERBOARD_COLLECTION", "leaderboard_winners")
    _mongo_lb = db[coll_name]
    try:
        _mongo_lb.create_index([("won_at", DESCENDING)])
    except Exception:
        pass
    return _mongo_lb


# Initialize Mongo client at app startup to avoid per-request creation
try:
    _ = _get_mongo_collection()
    print("🔗 MongoDB client initialized at startup")
except Exception as _e:
    # Defer error handling to actual usage routes, but log for visibility
    print(f"⚠️ MongoDB init skipped/failed: {_e}")


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


async def _emit_events(events, to_sid=None):
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
            await sio.emit("game_update", payload, to=to_sid)
            # New explicit stats update
            await sio.emit("update_stats", payload, to=to_sid)
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
                await sio.emit("game_output", payload, to=to_sid)
                # New explicit dialogue channel
                await sio.emit("dialogue", {**payload, "type": "dialogue"}, to=to_sid)
            continue

        if etype == "pause":
            payload = {
                "type": "game_pause",
                "text": "[[PAUSE]]",
                "options": [],
                "state": last_state,
            }
            await sio.emit("game_pause", payload, to=to_sid)
            await sio.emit("pause", {**payload, "type": "pause"}, to=to_sid)
            continue

        if etype in ("choices", "menu"):
            items = ev.get("items", [])
            payload = {
                "type": "game_menu",
                "text": "",
                "options": items,
                "state": last_state,
            }
            await sio.emit("game_menu", payload, to=to_sid)
            await sio.emit("menu", {**payload, "type": "menu"}, to=to_sid)
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
                await sio.emit("combat_update", payload, to=to_sid)
            continue

        if etype == "update_stats":
            payload = {
                "type": "update_stats",
                "text": "",
                "options": [],
                "state": ev.get("data", last_state),
            }
            await sio.emit("update_stats", payload, to=to_sid)
            continue

        if etype == "clear":
            await sio.emit("clear", {"type": "clear"}, to=to_sid)
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
            await sio.emit("scene", payload, to=to_sid)
            continue

        if etype == "prompt":
            # represent prompt as an update with state, frontend shows input
            payload = {
                "type": "game_update",
                "text": ev.get("label", ""),
                "options": [],
                "state": last_state,
            }
            await sio.emit("game_update", payload, to=to_sid)
            # Also emit a dedicated prompt event for UI binding
            await sio.emit(
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
    await sio.emit("game_update", payload, to=to_sid)


@sio.event
async def connect(sid, environ):
    # Capture device_id from headers or cookies
    did = environ.get("HTTP_X_DEVICE_ID") or ""
    if not did:
        try:
            raw_cookie = environ.get("HTTP_COOKIE", "")
            if raw_cookie:
                c = SimpleCookie()
                c.load(raw_cookie)
                if "device_id" in c:
                    did = c["device_id"].value
        except Exception:
            did = ""
    if did:
        sid_device[sid] = did

    # Create engine for this session
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
    await sio.emit("connected", {"ok": True}, to=sid)


@sio.event
async def disconnect(sid):
    engines.pop(sid, None)
    sid_device.pop(sid, None)


@sio.on("engine_start")
@sio.on("player_start")
async def on_engine_start(sid):
    # Set initial background to labyrinth.png for character creation
    from game.scene_manager import set_labyrinth_background

    initial_bg_event = set_labyrinth_background()
    await _emit_events([initial_bg_event], to_sid=sid)

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
    await _emit_events(events, to_sid=sid)


@sio.on("engine_action")
@sio.on("player_action")
async def on_engine_action(sid, data):
    eng = engines.get(sid)
    if not eng:
        return
    action = (data or {}).get("action") or ""
    payload = (data or {}).get("payload") or {}

    # Debug logging
    print(f"🎮 WEBAPP DEBUG: Received action={action}")
    print(
        f"🎮 WEBAPP DEBUG: Current engine phase={eng.s.phase}, subphase={eng.s.subphase}"
    )

    # Intercept web save to persist state without changing client UI
    if action == "town:save":
        try:
            # Prefer mapped device id from connect; fall back to payload
            device_id = (sid_device.get(sid) or "").strip()
            # If still missing, attempt from payload
            if not device_id:
                device_id = (payload.get("device_id") or "").strip()
            if not device_id:
                # Emit a gentle message and route back to town
                await _emit_events(
                    [
                        {"type": "dialogue", "text": "Cannot save: missing device ID."},
                    ],
                    to_sid=sid,
                )
                events = eng.handle_action("town", {})
                await _emit_events(events, to_sid=sid)
                return
            # Save current snapshot (fallback to minimal dict on error)
            try:
                state = eng.snapshot()
            except Exception:
                state = {
                    "phase": getattr(getattr(eng, "s", None), "phase", "town"),
                    "depth": getattr(getattr(eng, "s", None), "depth", 1),
                    "character": None,
                }
            coll = _get_mongo_collection()
            doc = {
                "device_id": device_id,
                "game_state": state,
                "updated_at": datetime.utcnow(),
            }
            coll.update_one({"device_id": device_id}, {"$set": doc}, upsert=True)
            # Tell the user and gate with a Continue so the message is visible
            await _emit_events(
                [
                    {"type": "dialogue", "text": "Game saved for this device."},
                    {"type": "pause"},
                    {"type": "menu", "items": [{"id": "town", "label": "Continue"}]},
                ],
                to_sid=sid,
            )
            return
        except Exception as e:
            # Print full traceback to diagnose recursion source
            try:
                import traceback as _tb

                print("💥 SAVE TRACE:\n" + _tb.format_exc())
            except Exception:
                pass
            await _emit_events(
                [
                    {"type": "dialogue", "text": f"Save failed: {e}"},
                ],
                to_sid=sid,
            )
            events = eng.handle_action("town", {})
            await _emit_events(events, to_sid=sid)
            return

    # Intercept main menu load to restore state from Mongo for this device
    if action == "main:load":
        try:
            device_id = (sid_device.get(sid) or "").strip()
            if not device_id:
                device_id = (payload.get("device_id") or "").strip()
            if not device_id:
                await _emit_events(
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
                await _emit_events(events, to_sid=sid)
                return
            coll = _get_mongo_collection()
            doc = coll.find_one({"device_id": device_id}, {"_id": 0})
            if not doc or not isinstance(doc.get("game_state"), dict):
                await _emit_events(
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
                await _emit_events(
                    [
                        {
                            "type": "dialogue",
                            "text": "Failed to load save data.",
                        }
                    ],
                    to_sid=sid,
                )
                events = eng.start()
                await _emit_events(events, to_sid=sid)
                return
            # On success, tell the player and show the appropriate screen (town)
            await _emit_events(
                [
                    {"type": "dialogue", "text": "Loaded saved game."},
                ],
                to_sid=sid,
            )
            # Render town menu
            events = eng.handle_action("town", {})
            await _emit_events(events, to_sid=sid)
            return
        except Exception as e:
            await _emit_events(
                [
                    {"type": "dialogue", "text": f"Load failed: {e}"},
                ],
                to_sid=sid,
            )
            events = eng.start()
            await _emit_events(events, to_sid=sid)
            return

    # Intercept review commit before normal engine handling
    if action == "review:commit":
        # Extract draft from engine state
        draft = getattr(getattr(eng, "s", None), "review_draft", {}) or {}
        rating = int(draft.get("rating", 0))
        text = draft.get("text") if isinstance(draft.get("text"), str) else None
        if rating < 1 or rating > 5:
            await _emit_events(
                [
                    {
                        "type": "dialogue",
                        "text": "Cannot submit: rating missing or invalid.",
                    },
                    {"type": "menu", "items": [("main:menu", "Back")]},
                ],
                to_sid=sid,
            )
            return
        # Perform submission
        try:
            res = submit_review(rating, text)
            msg = (
                f"Review submitted: rating {rating}/5. File: {res.path}"
                if res.path
                else "Review submitted."
            )
            await _emit_events(
                [
                    {"type": "dialogue", "text": msg},
                    {"type": "pause"},
                    {"type": "menu", "items": [("main:menu", "Continue")]},
                ],
                to_sid=sid,
            )
            # Clear draft after success
            try:
                eng.s.review_draft = {}
                eng.s.subphase = ""
            except Exception:
                pass
            return
        except ReviewError as e:
            await _emit_events(
                [
                    {"type": "dialogue", "text": f"Review failed: {e}"},
                    {"type": "menu", "items": [("main:menu", "Back")]},
                ],
                to_sid=sid,
            )
            return

    # Intercept Leaderboard open
    if action == "main:leaderboard":
        try:
            coll = _get_leaderboard_collection()
            cur = (
                coll.find({}, {"name": 1, "level": 1, "won_at": 1})
                .sort("won_at", DESCENDING)
                .limit(25)
            )
            items = []
            lines = ["=== Leaderboard — Dragon Slayers ==="]
            for doc in cur:
                name = doc.get("name", "Unknown")
                lvl = int(doc.get("level", 1))
                ts = doc.get("won_at")
                try:
                    ts_str = ts.strftime("%Y-%m-%d %H:%M UTC") if ts else ""
                except Exception:
                    ts_str = str(ts or "")
                label = f"{name} (Level {lvl}) — {ts_str}"
                items.append(
                    {"id": f"leader:detail:{str(doc.get('_id'))}", "label": label}
                )
            # If empty
            if not items:
                lines.append("No winners yet. Defeat the Dragon to join the legends!")
            # Emit header + menu
            evs = [{"type": "clear"}] + [
                {"type": "dialogue", "text": ln} for ln in lines
            ]
            evs.append(
                {
                    "type": "menu",
                    "items": items + [{"id": "main:menu", "label": "Back"}],
                }
            )
            await _emit_events(evs, to_sid=sid)
            return
        except Exception as e:
            await _emit_events(
                [
                    {"type": "dialogue", "text": f"Failed to load leaderboard: {e}"},
                    {"type": "menu", "items": [{"id": "main:menu", "label": "Back"}]},
                ],
                to_sid=sid,
            )
            return

    # Intercept Leaderboard detail view
    if action.startswith("leader:detail:"):
        try:
            _id = action.split(":", 2)[2]
            coll = _get_leaderboard_collection()
            doc = coll.find_one({"_id": ObjectId(_id)})
            if not doc:
                await _emit_events(
                    [
                        {"type": "dialogue", "text": "Entry not found."},
                        {
                            "type": "menu",
                            "items": [{"id": "main:leaderboard", "label": "Back"}],
                        },
                    ],
                    to_sid=sid,
                )
                return
            # Build a compact summary
            lines = [
                f"=== {doc.get('name','Unknown')} (Level {int(doc.get('level',1))}) ===",
                f"Class: {doc.get('clazz','Adventurer')}  |  Won: {doc.get('won_at')}",
            ]
            stats = doc.get("stats", {}) or {}
            lines.append(
                f"Monsters defeated: {int(stats.get('monsters_defeated',0))}  |  Quests completed: {int(stats.get('quests_completed',0))}"
            )
            lines.append(
                f"Potions used: {int(stats.get('potions_used',0))}  |  Spells used: {int(stats.get('spells_used',0))}"
            )
            lines.append(
                f"Gold earned: {int(stats.get('gold_earned',0))}  |  Gold spent: {int(stats.get('gold_spent',0))}"
            )
            lines.append(
                f"Weapon (current): {doc.get('current_weapon','Unarmed')}  |  Weapon (most used): {doc.get('most_used_weapon','Unarmed')}"
            )
            lines.append(f"Armor (current): {doc.get('current_armor','None')}")
            comp = doc.get("companion")
            if comp:
                cname = comp.get("name")
                cspecies = comp.get("species")
                lines.append(f"Companion: {cname} the {cspecies}")
            # Emit
            evs = [{"type": "clear"}] + [
                {"type": "dialogue", "text": ln} for ln in lines
            ]
            evs.append(
                {
                    "type": "menu",
                    "items": [
                        {"id": "main:leaderboard", "label": "Back"},
                        {"id": "main:menu", "label": "Main Menu"},
                    ],
                }
            )
            await _emit_events(evs, to_sid=sid)
            return
        except Exception as e:
            await _emit_events(
                [
                    {"type": "dialogue", "text": f"Failed to load entry: {e}"},
                    {
                        "type": "menu",
                        "items": [{"id": "main:leaderboard", "label": "Back"}],
                    },
                ],
                to_sid=sid,
            )
            return

    # Intercept automatic save on Dragon victory
    if action == "combat:dragon_victory_continue":
        try:
            device_id = (sid_device.get(sid) or "").strip()
            # Save snapshot
            state = eng.snapshot()
            coll = _get_mongo_collection()
            doc = {
                "device_id": device_id or str(uuid.uuid4()),
                "game_state": state,
                "updated_at": datetime.utcnow(),
            }
            coll.update_one({"device_id": doc["device_id"]}, {"$set": doc}, upsert=True)
            # Record leaderboard entry
            try:
                c = getattr(eng.s, "character", None)
                s = getattr(eng, "s", None)
                if c and s:
                    current_weapon = (
                        c.weapons[c.equipped_weapon_index].name
                        if 0 <= c.equipped_weapon_index < len(c.weapons)
                        else "Unarmed"
                    )
                    weapon_use = dict(getattr(s, "weapon_use", {}) or {})
                    most_used_weapon = None
                    if weapon_use:
                        most_used_weapon = max(
                            weapon_use.items(), key=lambda kv: kv[1]
                        )[0]
                    armor_name = c.armor.name if getattr(c, "armor", None) else "None"
                    lb = _get_leaderboard_collection()
                    entry = {
                        "device_id": device_id or None,
                        "won_at": datetime.utcnow(),
                        "name": c.name,
                        "clazz": c.clazz,
                        "level": c.level,
                        "xp": c.xp,
                        "attributes": dict(c.attributes or {}),
                        "current_weapon": current_weapon,
                        "most_used_weapon": most_used_weapon or current_weapon,
                        "current_armor": armor_name,
                        "weapons_owned": [
                            getattr(w, "name", str(w)) for w in (c.weapons or [])
                        ],
                        "armors_owned": [
                            getattr(a, "name", str(a)) for a in (c.armors_owned or [])
                        ],
                        "companion": (c.companion.__dict__ if c.companion else None),
                        "stats": {
                            "monsters_defeated": int(
                                getattr(s, "monsters_defeated", 0)
                            ),
                            "potions_used": int(getattr(s, "potions_used", 0)),
                            "spells_used": int(getattr(s, "spells_used", 0)),
                            "quests_completed": int(getattr(s, "quests_completed", 0)),
                            "gold_earned": int(getattr(s, "gold_earned", 0)),
                            "gold_spent": int(getattr(s, "gold_spent", 0)),
                        },
                    }
                    lb.insert_one(entry)
            except Exception as _e:
                print(f"⚠️ Leaderboard insert failed: {_e}")
        except Exception as e:
            print(f"⚠️ Auto-save on victory failed: {e}")
        # Continue to engine handling (epilogue)

    # Intercept automatic wipe on permanent death
    if action == "combat:revival_fail_continue":
        try:
            device_id = (sid_device.get(sid) or "").strip()
            if device_id:
                coll = _get_mongo_collection()
                coll.delete_one({"device_id": device_id})
        except Exception as e:
            print(f"⚠️ Auto-wipe on death failed: {e}")

    events = eng.handle_action(action, payload)

    print(
        f"🎮 WEBAPP DEBUG: After action, phase={eng.s.phase}, subphase={eng.s.subphase}"
    )
    print(f"🎮 WEBAPP DEBUG: Emitting {len(events)} events")

    await _emit_events(events, to_sid=sid)


if __name__ == "__main__":
    if not os.path.exists("static"):
        os.makedirs("static", exist_ok=True)
    port = int(os.getenv("PORT", "5000"))
    host = os.getenv("HOST", "0.0.0.0")
    debug = os.getenv("FLASK_DEBUG", "").lower() in ("1", "true", "yes")
    print(f"🚀 Starting ASGI server with uvicorn on {host}:{port} (debug={debug})...")
    try:
        import uvicorn

        uvicorn.run(
            asgi_app, host=host, port=port, log_level="debug" if debug else "info"
        )
    except Exception:
        app.run(host=host, port=port, debug=debug)
