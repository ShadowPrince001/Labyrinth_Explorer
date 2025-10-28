
# Labyrinth Adventure — Web UI (event-driven)

A compact Python labyrinth crawler with a modern browser UI. The app uses a structured, event-driven engine (no stdout scraping) over Socket.IO; the frontend renders dialogue with typed pacing and menus as buttons.

## Features

- Character creation with 5d4 attribute rolls; HP and Gold based on rules and dialogue-driven narration
- Town hub: Shop, Healer, Tavern, Eat, Gamble, Temple (Divine), Level Up, Quests, Train, Sleep, Companion, Repair, Remove Curses, Save
- Labyrinth exploration: generated rooms, traps, ambient flavor, chests, rare item drops, and monster encounters
- Turn-based combat with aimed attacks, potions, spells, divine aid, charm, run, and examine; XP/leveling and loot
- Web UI: button-driven menus, character-by-character reveal, and a compact HUD (can be toggled off)

## Run the web app

```powershell
python -m venv .venv ; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# (Optional) build the frontend assets (React JSX → JS)
npm ci
npm run build

python .\web_app.py
```

Then open http://127.0.0.1:5000/ in your browser.

Note: The legacy CLI entry point (`python -m game`) has been removed. Use the web app.

## Dev quick-start

- Python deps: `pip install -r requirements.txt`
- Frontend build: `npm ci && npm run build` (compiles `static/app.jsx` to `static/app.js`)
- Start server: `python .\web_app.py` → open http://127.0.0.1:5000/

## Diagnostics and tests

- Syntax/import check (all .py): `python tools/check_all.py`
- Dialogue key coverage: `python tools/check_dialogue_references.py`
- Import smoke: `python tools/import_smoke_test.py`
- Combat log tests: `python tools/test_log_strings.py`
- Shop/town flows: `python tools/shop_flow_test.py`, `python tools/shop_purchase_sell_test.py`, `python tools/town_flow_test.py` (some legacy tests may reference removed CLI functions and can be skipped)

## Tips

- All player-facing text comes from `data/dialogues.json` where possible.
- Add content in `data/` (monsters, items, traps, spells) to extend the game.
- The web engine lives in `game/engine.py` and emits events the server forwards to the client.

Localization note: Most roll/result strings are now data-driven. Recent additions include keys for town refresh gating and sleep outcomes (e.g., `town.refresh_used`, `town.sleep_success`, `town.sleep_fail`), and creation narration such as `system.gold_result_detailed`.

See `PROJECT_OVERVIEW.txt` for a full file-by-file breakdown.