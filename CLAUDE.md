# LNFP Poster Generator — Claude Context

## Goal

This is a Flask web app that generates high-resolution Tunisian football match posters as PNG images. It supports Arabic RTL text, Ligue 1, Ligue 2 pools, fixtures, results, standings, broadcasters, authentication, Firebase/local persistence, and optional live-score providers.

## Read-first rule

Do **not** scan the whole repository. Start with this file, then inspect only the files relevant to the requested change.

The canonical runnable source is the **repository root**:

- `run.py` — local entry point.
- `wsgi.py` — production entry point.
- `config.py` — environment-driven configuration.
- `app/` — active Flask application.
- `render.yaml` and `Procfile` — Render deployment.

There are historical/duplicate copies under `foot-main/` and `imported/foot-main/`. Do not edit those unless the user explicitly asks for them or the running deployment is confirmed to use one of them. The root deployment uses `wsgi:app`.

## Architecture

| Area | File | Responsibility |
|---|---|---|
| App factory | `app/__init__.py` | Creates Flask app, store, admin service, and registers blueprints. |
| HTML pages | `app/routes/views.py` | `/`, `/studio`, `/live`, `/ranking`. |
| JSON/API | `app/routes/api.py` | Teams, parsing, preview, PNG generation, standings, matchdays, live APIs. |
| Admin | `app/routes/admin.py` | Login, logout, admin account management. |
| Poster renderer | `app/services/poster.py` | Pillow drawing, layout, colors, fonts, logos, Arabic text, PNG output. |
| Team registry | `app/services/teams.py` | Loads teams, competitions, channels, squads, backgrounds. |
| Fixture parser | `app/services/fixtures_parser.py` | Parses pasted/PDF fixture bulletins. |
| Results parser | `app/services/results_parser.py` | Parses result bulletins. |
| Live scores | `app/services/livescore.py` | TheSportsDB/API-Football integration and caching. |
| Persistence | `app/services/store.py` | RTDB, Firestore, or local JSON fallback. |
| Frontend controller | `app/static/js/app.js` | Studio state, match rows, team picker, preview, save/load. |
| Frontend styles | `app/static/css/style.css` | RTL responsive layout and visual styling. |
| Studio template | `app/templates/index.html` | Poster editor UI and fields. |
| Static data | `app/data/*.json` | Teams, competitions, channels, and squads. |

## Poster generation flow

1. The user edits the studio in `app/templates/index.html` and `app/static/js/app.js`.
2. The browser sends a normalized payload to `POST /api/preview` or `POST /api/generate`.
3. `app/routes/api.py` validates and normalizes title, date, teams, stadium, channels, mode, background, and logo.
4. `app/services/poster.py` renders the poster on a native **2000×2500** canvas.
5. `/api/preview` returns a downscaled PNG; `/api/generate` returns the full-resolution downloadable PNG.

For a new visual field, normally update all four layers: HTML field, JavaScript state/payload, API normalization, and Pillow drawing.

## Most common change locations

- Change poster layout/colors/positions: `app/services/poster.py`.
- Change studio behavior or add an input: `app/static/js/app.js` and `app/templates/index.html`.
- Change team names, stadiums, or logos: `app/data/teams.json` or the relevant Ligue 2 JSON file.
- Add a competition: `app/data/competitions.json`, then check `app/services/teams.py` and `app/routes/views.py`.
- Add a TV channel: `app/data/channels.json` and `app/static/tv/`.
- Add/change an API operation: `app/routes/api.py`.
- Change authentication/admin behavior: `app/auth.py`, `app/routes/admin.py`, `app/services/admins.py`.

## Important implementation rules

- Preserve Arabic RTL rendering and RAQM fallback behavior in `poster.py`.
- Keep the native poster dimensions at 2000×2500 unless the user explicitly requests a format change.
- Keep legitimate parentheses in stadium names. Only remove known accidental trailing placeholders such as `(:)` or `:)`.
- Do not put secrets, Firebase JSON, API keys, or passwords in Git.
- Use environment variables for deployment configuration.
- The local JSON store is fallback storage and can be ephemeral on Render; Firebase is required for durable production data.
- When changing a payload field, keep preview, generate, save/load, and parser paths consistent.
- Do not modify duplicate directories as a workaround without identifying which entry point is running.

## Development commands

```bash
python3 -m compileall -q app run.py wsgi.py config.py
python3 run.py
curl -s http://127.0.0.1:5000/healthz
```

The health endpoint is public and should return `{"status":"ok", ...}`. Protected studio/API routes require an authenticated session.

## Key API endpoints

- `GET /healthz`
- `GET /api/teams`
- `GET /api/competitions`
- `POST /api/preview`
- `POST /api/generate`
- `POST /api/parse-fixtures`
- `POST /api/parse-results`
- `GET /api/live/scoreboard`
- `GET /api/live/standings`
- `GET|POST|DELETE /api/matchdays...`

## Current repository note

The latest relevant commit removes stray stadium punctuation from all three poster-renderer copies:

`ee5ce9b Remove stray stadium punctuation from posters`

Before committing, run `git diff --check`, compile the Python files, and test the specific changed path. Keep commits focused and use a descriptive message.
