"""
Flask + Socket.IO backend for event-driven Labyrinth Adventure.

This server does NOT capture stdout or use input(). Instead, it maintains a
GameEngine instance per Socket.IO client and relays structured JSON events
to the frontend. The frontend sends back actions to drive the engine.
"""

from flask import Flask, send_from_directory, request
from flask_socketio import SocketIO, emit
from typing import Dict
import os

from game.engine import GameEngine

app = Flask(__name__, static_folder="static")
socketio = SocketIO(
    app,
    async_mode="threading",
    cors_allowed_origins="*",
    logger=True,
    engineio_logger=True,
    transports=["polling"],
    allow_upgrades=False,
)

# Keep engine instances per client session (sid)
engines: Dict[str, GameEngine] = {}


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


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
    engines[sid] = GameEngine()
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

    events = eng.handle_action(action, payload)

    print(
        f"🎮 WEBAPP DEBUG: After action, phase={eng.s.phase}, subphase={eng.s.subphase}"
    )
    print(f"🎮 WEBAPP DEBUG: Emitting {len(events)} events")

    _emit_events(events, to_sid=sid)


if __name__ == "__main__":
    if not os.path.exists("static"):
        os.makedirs("static", exist_ok=True)
    print("🚀 Starting Flask-SocketIO server...")
    socketio.run(app, host="127.0.0.1", port=5000, debug=True)
