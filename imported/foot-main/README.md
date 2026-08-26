# LNFP — مولّد الأفيشات الرسمية · Official Match-day Poster Generator

An enterprise-grade Flask web app that turns the empty **“BG vide”** template
into a finished Tunisian **Ligue 1 (LNFP)** match-day poster — exactly like the
provided reference. Pick teams by **name or crest**, and the kick-off time,
stadium and Arabic date fill in automatically. The finished poster is rendered
**entirely server-side** (no external photo editor) and downloads as a
high-resolution PNG.

<p align="center">
  <em>Choose fixtures → live preview → download PNG. All inside the app.</em>
</p>

---

## ✨ Features

- **Fill the template automatically** — LNFP crest (brand gold) on top, Arabic
  title, decorated date bar, and one card per fixture with both crests, the
  kick-off time and the stadium — laid out to match the reference poster.
- **Pick by name *or* logo** — a searchable dropdown shows each club’s crest and
  its Arabic/French name; selecting the home team auto-fills its home stadium.
- **Automatic Arabic dates** — an ISO date becomes e.g. `الأحد 23 أوت 2026`
  (Tunisian month names), computed identically on the client and server.
- **Live preview + one-click download** — full 2000×2500 PNG, generated with
  Pillow + RAQM (HarfBuzz) so Arabic text is correctly shaped and joined.
- **Save & reuse** — admins, saved match-days (scoring) and standings (ranking)
  persist to **Google Firebase (Realtime Database, with Firestore as an
  alternative)**, with an automatic **local JSON fallback** so the app runs
  before Firebase is wired up.
- **Live scoring** — a `/live` Ligue 1 scoreboard, plus one-click fill of a
  *Résultats* poster or the standings table from live data. Works out of the box
  via **TheSportsDB** (free, current season) with **API-Football** as an
  optional in-play upgrade.
- **Responsive** — a two-column workspace on desktop, stacked on mobile.
- **Deploy-ready for Render** — `render.yaml`, `Procfile`, `runtime.txt`.

---

## 🗂 Project structure

```
foot/
├── run.py                     # local dev entry  (python run.py)
├── wsgi.py                    # production entry  (gunicorn wsgi:app)
├── config.py                  # env-driven configuration
├── requirements.txt
├── Procfile / render.yaml / runtime.txt
├── app/
│   ├── __init__.py            # application factory
│   ├── routes/
│   │   ├── views.py           # HTML page
│   │   └── api.py             # JSON API + poster rendering
│   ├── services/
│   │   ├── poster.py          # ← the poster renderer (Pillow + RAQM)
│   │   ├── teams.py           # team registry loader
│   │   ├── dates.py           # Arabic (Tunisian) date formatting
│   │   ├── store.py           # RTDB / Firestore / local-JSON persistence
│   │   └── firebase_service.py
│   ├── data/teams.json        # 16 clubs: names (ar/fr), crest, home stadium
│   ├── templates/             # base.html, index.html, icons/*.svg
│   └── static/
│       ├── css/style.css      # branded, RTL, responsive
│       ├── js/app.js          # builder controller
│       ├── fonts/CairoVar.ttf # bundled Arabic font
│       ├── img/               # LNFP logo, BG template, favicon (SVG)
│       └── logos/             # team crests (svg rasterised to png)
└── logo_equipe/, BG vide.png, Exemple.PNG, LOGO LNFP.png   # original sources
```

---

## 🚀 Run locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # optional; defaults work out of the box
python run.py                 # http://localhost:5000
```

Without any configuration the app uses the **local JSON store**
(`data/matchdays.json`) — you can generate and download posters immediately.

---

## 🔥 Enable Google Firebase

Everything worth keeping — admin accounts, saved match-days (**scoring**) and
standings (**ranking**) — is backed up to Firebase. The app prefers the
**Realtime Database (RTDB)** and falls back to **Firestore**, then to a local
JSON file. One service-account credential authenticates whichever you use and
**bypasses the database rules**, so you can leave the RTDB rules locked
(`.read`/`.write: false`).

1. In the [Firebase console](https://console.firebase.google.com/) open your
   project and, under **Build → Realtime Database**, note its URL, e.g.
   `https://<project>-default-rtdb.<region>.firebasedatabase.app/`. Set it as
   `FIREBASE_DB_URL` (the app already defaults to this project's URL).
2. Give the app a way to authenticate — **pick one**:
   - **Database secret (simplest).** Project settings → *Service accounts* →
     **Database secrets** → copy the secret, and set it as `FIREBASE_DB_SECRET`.
     It talks to RTDB over REST, bypasses the rules, and needs no service
     account. *(Firebase marks these "legacy" but they still work.)*
   - **Service account (also enables Firestore).** *Generate new private key*
     for a JSON file, then set either `FIREBASE_CREDENTIALS_JSON` (the whole
     JSON on one line — best for Render) or
     `GOOGLE_APPLICATION_CREDENTIALS=./serviceAccount.json`.
3. (Optional) `DB_BACKEND=rtdb` (or `firebase`) to require Firebase, or leave it
   `auto`. To use **Firestore instead** of RTDB, leave `FIREBASE_DB_URL` blank
   and provide a service-account credential.

> ⚠️ The `FIREBASE_DB_URL` alone is **not** enough — without a
> `FIREBASE_DB_SECRET` (or a service-account credential) the app cannot
> authenticate and quietly falls back to the local JSON store, which is wiped on
> every Render restart. The admin panel and the sidebar dot show the live
> connection state so you can confirm it worked.

The health endpoint reports the active backend:

```bash
curl localhost:5000/healthz
# {"status":"ok","store":{"backend":"rtdb", ...}}
```

> Prefer **Neon (Postgres)** instead? The persistence layer is isolated in
> `app/services/store.py` behind a small CRUD interface — add a `NeonStore` with
> the same methods and select it in `create_app`.

---

## ⚽ Enable live scoring

Live Ligue 1 data powers three things:

- a **`/live` scoreboard** (manual refresh, shows the remaining daily quota),
- **«جلب النتائج»** in the studio to fill a *Résultats* poster from a day's
  fixtures, and
- **«جلب من API»** in the ranking editor to fill points/played from the table.

Two providers are supported (`LIVE_PROVIDER`):

### TheSportsDB — free, works out of the box (default)
No key or signup needed: the public key `3` covers the **current** Tunisian
Ligue 1 season for **results and the league table**. This is the default when no
API-Football key is set, so live scoring works immediately on deploy. Real-time
in-play is Patreon-only there, so scores appear once matches finish — which is
all a poster/standings tool needs. Override `THESPORTSDB_KEY` only if you have
your own; `THESPORTSDB_LEAGUE_ID` defaults to **4828**.

### API-Football — optional upgrade for true in-play
Create a key at [dashboard.api-football.com](https://dashboard.api-football.com/)
and set `APIFOOTBALL_KEY` (and `LIVE_PROVIDER=apifootball` or `auto`). League id
defaults to **202**.

> ⚠️ API-Football's **free** plan is limited to **past seasons**, so the current
> season may not appear on it — use TheSportsDB (the default) for the live
> season, or upgrade API-Football for real-time in-play.

Everything degrades gracefully and never 500s: on any provider error the
scoreboard shows the reason and the auto-fill buttons report it. Upstream calls
are cached in-process (`APIFOOTBALL_LIVE_TTL` / `APIFOOTBALL_STATIC_TTL`) so a
matchday costs only a handful of requests, and club names are matched to the
roster by name (unmatched clubs are skipped).

---

## ☁️ Deploy to Render

**Blueprint (one click):** push this repo to GitHub, then in Render choose
**New → Blueprint** and point it at the repo — `render.yaml` provisions the web
service. After the first deploy, add `FIREBASE_DB_SECRET` (or
`FIREBASE_CREDENTIALS_JSON`) in the service’s *Environment* tab to switch
persistence to the Realtime Database (`FIREBASE_DB_URL` already defaults to this
project's database).

**Manual:** create a **Web Service** with
- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn wsgi:app --workers 2 --threads 4 --timeout 120 --bind 0.0.0.0:$PORT`

---

## 🔌 API reference

| Method & path              | Purpose                                             |
|----------------------------|-----------------------------------------------------|
| `GET  /api/teams`          | All clubs (code, ar/fr name, crest, stadium)        |
| `GET  /api/team/<code>`    | A single club                                       |
| `GET  /api/channels`       | Broadcasters and the per-match cap                  |
| `POST /api/preview`        | Rendered PNG for the live preview (downscaled)      |
| `POST /api/generate`       | Full-resolution PNG as a download                   |
| `GET  /api/matchdays`      | List saved match-days                               |
| `POST /api/matchdays`      | Save a match-day                                    |
| `GET  /api/matchdays/<id>` | Fetch a saved match-day                             |
| `DELETE /api/matchdays/<id>`| Delete a saved match-day                           |
| `GET  /api/status`         | Active persistence backend                          |
| `GET  /healthz`            | Health check (used by Render)                       |

**Render payload** (`/api/preview` and `/api/generate`):

```json
{
  "title": "تعيينات مباريات\nالجولة الأولى ذهاب\nلبطولة الرابطة 1",
  "date_iso": "2026-08-23",
  "matches": [
    { "home": "est", "away": "ess", "time": "16:30", "stadium_ar": "حمادي العقربي برادس" }
  ]
}
```

`home`/`away` are team **codes** from `app/data/teams.json`. `stadium_ar` is
optional — when omitted the home team’s stadium is used.

---

## 🔤 Using the federation fonts

The poster uses two faces: **YaModernPro-Bold** for text and **FWC2026** for
kick-off times. Both are supplied and live in `app/static/fonts/`; the app
resolves each role independently and falls back to the bundled Cairo if a file
is ever missing:

| Role | Used for | Drop-in file name |
|------|----------|-------------------|
| text | title, club names, stadiums | `YaModernPro-Bold.otf` (or `.ttf`) |
| time | kick-off times and the date bar | `FWC2026.otf` (or `.ttf`) |

Also accepted: `YaModernPro.otf/.ttf` (text); `FWC2026-Bold`, `FWC2026-Regular`,
`FWC 2026`, or `Ya Modern Pro Bold` (time). To point at other files, set
`POSTER_FONT_TEXT` / `POSTER_FONT_TIME` (absolute, or relative to
`app/static/fonts/`); `POSTER_FONT` sets both.

**FWC2026 carries no Arabic glyphs** (Latin and figures only), so anything
containing Arabic — the date bar, for instance — is routed to the text face
automatically; kick-off times are digits and stay on the numeric face.

Confirm which faces are live:

```bash
curl -s localhost:5000/api/status
# ..."fonts":{"text":"YaModernPro-Bold.otf","time":"FWC2026.otf"}
```

## 🔐 Administrator accounts

**The whole studio requires a sign-in.** Signed out, `/` is the login page;
`/studio` redirects there and every data/poster endpoint answers `401`. Only
`/healthz` and the static assets stay public.

Two roles share one session:

| Role | May do |
|------|--------|
| `super` | manage accounts (`/admin`) **and** use the studio |
| `admin` | use the studio only |

Once signed in as the super administrator, `/admin` is a control panel that can
**create, reset, suspend, reactivate and remove** administrator accounts, with
live counts of total / active / suspended. Suspending or deleting an account
locks it out on its next sign-in attempt.

Set the super-admin credentials in the environment:

```
SUPER_ADMIN_USER=superadmin
SUPER_ADMIN_PASSWORD=<a long random password>
```

If `SUPER_ADMIN_PASSWORD` is unset the app **generates a random password at
start-up and prints it once to the log** — so an unconfigured deployment is
never reachable with a guessable default. On Render, set the variable in the
service's *Environment* tab and redeploy.

Security notes:

- Passwords are stored only as PBKDF2 hashes (Werkzeug); the API never returns
  a hash or a plaintext password.
- The generated password comes from a CSPRNG and omits ambiguous glyphs; it is
  shown once, with a copy button, and cannot be read back afterwards.
- Sign-in is throttled per client address (6 attempts / 5 minutes).
- Session cookies are HttpOnly, SameSite=Lax and Secure by default; set
  `SESSION_COOKIE_SECURE=0` for plain-HTTP local runs.
- Accounts live in their own Firestore collection / JSON file, never mixed
  with poster data. **On Render's free tier the local file is ephemeral**, so
  configure Firebase if the accounts must survive a restart.

## 📺 Broadcasters

Each fixture can carry up to **four** broadcaster marks, shown in a row under
the ground name. The registry lives in `app/data/channels.json` and the marks
in `app/static/tv/`; `max_per_match` there sets the cap, which the API enforces
as well as the UI.

Add a channel by dropping its logo into `app/static/tv/` and adding an entry:

```json
{ "code": "mychannel", "name_ar": "قناتي", "logo": "mychannel.png" }
```

Marks are fitted individually rather than to a common height: they range from a
5.8:1 banner to a 0.7:1 upright, so a shared height would let the widest one
swamp the row. The row is then centred and, if the selection is too wide for
the bar, scaled down as a whole.

## 🖼 How uploaded crests are adapted

Any crest — built-in or uploaded — is fitted to the badge box automatically and
**its colours are never altered**:

1. a flat backing plate (a JPEG/PNG on solid white or one colour) is detected
   from the corners and made transparent, with thresholds derived from the
   image's own contrast, so even white-on-off-white artwork survives;
2. the extracted opacity is normalised so strokes read as solid rather than
   ghosted;
3. dead margins are trimmed and the artwork is scaled to fill the box, so every
   crest lands at a similar visual weight.

## 🏆 Competitions and the header badge

`app/data/competitions.json` holds the presets shown in the **المسابقة**
dropdown; each supplies a default title and badge, and both stay editable in
the UI. The badge is never recoloured — built-in artwork and uploaded crests
render with their own colours. Upload a crest with **رفع شعار** to brand a
competition without redeploying (it travels inline with the render request,
which keeps it working on Render's ephemeral disk).

## 🎨 Customising the data

- **Clubs / names / stadiums:** edit `app/data/teams.json`.
- **Poster layout / colours:** all drawing lives in `app/services/poster.py`
  (coordinates are on the native 2000×2500 canvas).
- **Add a club crest:** drop a PNG in `app/static/logos/<code>.png` and add the
  club to `teams.json`.
