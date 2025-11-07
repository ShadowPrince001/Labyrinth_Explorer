
# Labyrinth Adventure — Web UI (event-driven)

A compact Python labyrinth crawler with a modern browser UI. The app uses a structured, event-driven engine (no stdout scraping) over Socket.IO; the frontend renders dialogue with typed pacing and menus as buttons.

## Features

* External review & rating system: From the main menu select "Review" to submit a required rating (1–5) and optional text. Each review becomes a standalone text file committed to the GitHub repository (folder `reviews/`). Reviews are not viewable in‑game; open the repo on GitHub to read them.

* Leaderboard of winners: From the main menu select "Leaderboard" to view recent characters who defeated the Dragon. Entries show level, date, and a detail view with run statistics (monsters defeated, quests completed, potions/spells used, gold earned/spent, equipment, and companion). The game auto‑saves on victory and auto‑wipes the save on permanent death.

- Equipment damage: Weapons/armor can be damaged (5% on relevant events). Repairs cost 30g at the weaponsmith.
- Magic gear drops: 25% chance after victories. Rings bind and apply attribute changes immediately; labyrinth gear (weapons/armor) is unsellable.

### Review submission environment variables

To enable committing reviews directly to GitHub you must define the following environment variables (locally in `.env`, in Render dashboard, and/or as repo variables/secrets for CI):

| Variable | Required | Description |
|----------|----------|-------------|
| `GITHUB_TOKEN` | Yes | Personal access token with permission to write contents to the target repo (classic: `repo`, or fine‑grained: contents:write). In GitHub Actions you can reuse the built‑in token ONLY if committing to the same repo. |
| `GITHUB_REPO` | Yes | Target repository in `owner/repo` form (e.g. `ShadowPrince001/Labyrinth_Explorer`). |
| `GITHUB_REVIEWS_PATH` | No | Subfolder for review files (default `reviews`). |
| `GITHUB_REVIEWS_BRANCH` | No | Branch name to commit to (defaults to repo default branch). |

If `GITHUB_TOKEN` or `GITHUB_REPO` are missing, the review submission flow will display an error instead of committing a file.

Example `.env` entries:

```
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
GITHUB_REPO=ShadowPrince001/Labyrinth_Explorer
GITHUB_REVIEWS_PATH=reviews
GITHUB_REVIEWS_BRANCH=main
```

You can run `python tools/check_review_env.py` to verify required variables are present before starting the server.

## Run the web app

```powershell
python -m venv .venv ; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Build the frontend assets (React JSX → JS)
npm ci
npm run build

python .\web_app.py
```

Then open http://127.0.0.1:5000/ in your browser.

Note: The legacy CLI entry point (`python -m game`) has been removed. Use the web app.

### Persistence (MongoDB)

Saved games and the leaderboard are stored in MongoDB.

Required variables (example defaults provided in `.env.example`):

```
MONGODB_URI=mongodb+srv://user:pass@cluster.example.mongodb.net/?retryWrites=true&w=majority
MONGODB_DB=labyrinth
MONGODB_COLLECTION=player_saves
MONGODB_LEADERBOARD_COLLECTION=leaderboard_winners
```

Auto‑save on win: triggers when you continue after defeating the Dragon and also inserts a leaderboard entry.

Auto‑wipe on death: triggers when revival fails and removes your save for the current device.

Saves and the leaderboard live in the same database (separate collections), using the same MongoDB connection.

## Responsive scene images (no UI changes)

- Background/foreground scene images are rendered with `<img>` layers using `object-fit: contain` and centered alignment to prevent any cropping on mobile and desktop.
- Images are constrained to the viewport with `max-width: 100vw` and `max-height: 100vh` and do not overflow horizontally or vertically.
- The dynamic textbox (auto-resizing, buttons, starting position, and interactions) is unchanged; only the image container implementation was adjusted.
- The container uses modern viewport units where available (`height: 100dvh`) with a `100vh` fallback to avoid mobile browser UI cropping.

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

Localization note: Most roll/result strings are data-driven. Examples include keys for town refresh gating and sleep outcomes (e.g., `town.refresh_used`, `town.sleep_success`, `town.sleep_fail`), and creation narration such as `system.gold_result_detailed`.

For a technical architecture and structure guide, see `project_overview.md`.
For game systems and rules, see `mechanics.md`.