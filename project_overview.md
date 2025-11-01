# Project Overview

This document describes the technical architecture, key modules, project structure, and development workflow for Labyrinth Adventure (Web UI).

## Architecture

- Backend: Python (Flask + Flask-SocketIO)
  - Entry point: `web_app.py` (serves static files, hosts Socket.IO, forwards engine events to client)
  - Game engine: `game/engine.py` (event-driven state machine emitting events: dialogue, menu, pause, scene, update_stats, etc.)
  - Data: JSON files in `data/` for monsters, items, spells, traps, dialogues, etc.
- Frontend: React (UMD) rendered from `static/index.html`
  - Source: `static/app.jsx` (compiled with Babel to `static/app.js`)
  - Socket.IO client receives events and renders: typed dialogue, menus, prompts, HUD, and background scenes with smooth transitions.

## Event Flow

1. Client connects; server starts the engine (`engine.start()`), which emits initial events.
2. Client renders events and user clicks buttons.
3. Client sends actions (e.g., `"town:shop"`, `"combat:attack"`) back to server.
4. Engine updates state and emits new events.

All text intended for the user is carried via events instead of printing to stdout.

## Key Modules

- `web_app.py` — Flask-SocketIO server, static hosting, and event bridging.
- `game/engine.py` — Core game flow:
  - Phases: main_menu, select_difficulty, create_name, create_attrs, town, dungeon, combat.
  - Combat options: attack/aim/weapon, use_potion, cast_spell, divine, charm, run, examine.
  - Rewards: XP and gold based on `data/monsters.json` (XP uses `xp`, gold sampled from `gold_range`); both multiplied by depth on kills. Charm success grants 50% of these depth-scaled rewards without quests/drops.
  - Room generation, traps, and chests via `game/labyrinth.py` and `game/traps.py`.
- `game/entities.py` — Character, Monster, and item data structures.
- `game/data_loader.py` — JSON loaders and helper accessors.
- `static/index.html` — HTML host for the UI and loader for `app.js`.
- `static/app.jsx` — React client (debounced scene transitions, mobile gesture suppression, typed text, compact overlay).
- `data/` — Game content (monsters, items, spells, dialogues, etc.).
- `tools/` — Diagnostic scripts and smoke tests.

## Project Structure

```
/ (root)
  README.md
  project_overview.md
  mechanics.md
  requirements.txt
  package.json
  web_app.py
  /game
    engine.py, entities.py, ...
  /data
    monsters.json, dialogues.json, ...
  /static
    index.html, app.jsx, app.js, images/
  /tools
    *.py smoke/tests, utilities
```

## Development

- Python: `pip install -r requirements.txt`
- Frontend build: `npm ci && npm run build` (compiles `static/app.jsx` to `static/app.js`)
- Run: `python web_app.py` → Open `http://127.0.0.1:5000/`

## Backgrounds & Transitions

- Backgrounds are cross-faded using a dual image layer and preloading to avoid flashes.
- Mobile gestures (pinch/double-tap zoom) are suppressed for consistent touch gameplay.
- Monster images bias top framing via `object-position: top center`.
- Overlay/text box focuses on legibility and comfort:
  - Subtle dark overlay (rgba(20,20,20,0.35)) with a gentle blur (backdrop-filter: 2px) to separate text from busy scenes without over-dimming.
  - Off-white, heavier sans-serif text with a soft shadow for readability.
  - Compact buttons with muted colors, subtle borders, and accessible focus outlines.

## Data & Content

- All player-facing lines are mapped in `data/dialogues.json` where possible.
- Adding new enemies/items requires only JSON edits, no engine code.

## Tests & Diagnostics

- Run quick checks under `tools/` (e.g., `check_all.py`, `import_smoke_test.py`, flow tests).
- Most tests are smoke-style and can be run independently.

## Images & Asset Notes

- Scene images live under `static/images/*`; backgrounds are referenced by name via scene events from the engine.
- Image framing uses `object-fit: cover` for backgrounds and prioritizes the top when showing monster portraits.
- For adding or replacing images, prefer modern formats (PNG/WebP); keep aspect ratios consistent with existing assets to minimize cropping.

## Notes

- The CLI entry path was replaced by the web engine; all interactions flow via events.
- Depth scaling for XP/gold and charm reward rules are implemented in `engine.py`.
