"""Application configuration.

Values are read from environment variables so the same codebase runs
locally, on Render, or anywhere else without edits. Copy ``.env.example``
to ``.env`` for local development.
"""
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:  # python-dotenv optional in some environments
    pass


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production")

    # Which persistence backend to use: "auto" | "firebase" | "local".
    # "auto" uses Firebase when credentials are present, otherwise a local
    # JSON file — so the app always boots, even before Firebase is wired up.
    DB_BACKEND = os.environ.get("DB_BACKEND", "auto")

    # Firebase / Firestore. Provide EITHER a path to a service-account file
    # (GOOGLE_APPLICATION_CREDENTIALS) OR the JSON inline
    # (FIREBASE_CREDENTIALS_JSON) — the latter is convenient on Render.
    FIREBASE_CREDENTIALS_JSON = os.environ.get("FIREBASE_CREDENTIALS_JSON")
    GOOGLE_APPLICATION_CREDENTIALS = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    FIRESTORE_COLLECTION = os.environ.get("FIRESTORE_COLLECTION", "matchdays")

    # Realtime Database. When this URL is set the app backs everything up to
    # RTDB instead of Firestore. The URL is not a secret.
    FIREBASE_DB_URL = os.environ.get(
        "FIREBASE_DB_URL",
        "https://foot-99dee-default-rtdb.europe-west1.firebasedatabase.app/")

    # Simplest way to authenticate to RTDB: a legacy database secret (Firebase
    # console → Project settings → Service accounts → Database secrets). It is
    # used as ``?auth=<secret>`` on the REST API and bypasses the database
    # rules, so the rules can stay locked. When set, it is preferred over the
    # service-account credential below (no service-account JSON needed).
    FIREBASE_DB_SECRET = os.environ.get("FIREBASE_DB_SECRET")

    # --- Live scoring --------------------------------------------------
    # Which data provider to use:
    #   "auto"        -> API-Football if a key is set, else TheSportsDB (free)
    #   "thesportsdb" -> always TheSportsDB (free, no key needed, current season)
    #   "apifootball" -> always API-Football (needs a key; true in-play scores)
    LIVE_PROVIDER = os.environ.get("LIVE_PROVIDER", "auto")

    # TheSportsDB: free, covers the CURRENT Tunisian Ligue 1 season for results
    # and the league table. The public test key "3" needs no signup; put your
    # own free key here if you have one. (Real-time in-play is Patreon-only, so
    # scores appear once matches finish — enough for posters and standings.)
    THESPORTSDB_KEY = os.environ.get("THESPORTSDB_KEY", "3")
    THESPORTSDB_BASE_URL = os.environ.get(
        "THESPORTSDB_BASE_URL", "https://www.thesportsdb.com")
    THESPORTSDB_LEAGUE_ID = os.environ.get("THESPORTSDB_LEAGUE_ID", "4828")

    # API-Football (api-sports.io). Optional upgrade for true in-play scores.
    # NOTE: the FREE plan is limited to past seasons, so the current season may
    # not appear — TheSportsDB is the free way to get the live season.
    # Get a key at dashboard.api-football.com (100 requests/day).
    APIFOOTBALL_KEY = os.environ.get("APIFOOTBALL_KEY")
    APIFOOTBALL_BASE_URL = os.environ.get(
        "APIFOOTBALL_BASE_URL", "https://v3.football.api-sports.io")
    # Tunisian Ligue Professionnelle 1 is league 202 in API-Football.
    APIFOOTBALL_LEAGUE_ID = int(os.environ.get("APIFOOTBALL_LEAGUE_ID", "202"))
    # Season is the starting year (2026 = season 2026/2027). Blank -> derived
    # from today's date (Tunisian season starts in the summer).
    APIFOOTBALL_SEASON = os.environ.get("APIFOOTBALL_SEASON", "")
    # Cache windows (seconds) that keep the 100/day free budget from draining:
    # live data is fetched at most this often and shared across all viewers.
    APIFOOTBALL_LIVE_TTL = int(os.environ.get("APIFOOTBALL_LIVE_TTL", "90"))
    APIFOOTBALL_STATIC_TTL = int(os.environ.get("APIFOOTBALL_STATIC_TTL", "900"))

    # Local JSON fallback store.
    LOCAL_DB_PATH = os.environ.get(
        "LOCAL_DB_PATH",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "matchdays.json"),
    )

    FIRESTORE_ADMIN_COLLECTION = os.environ.get(
        "FIRESTORE_ADMIN_COLLECTION", "admins")

    # --- super administrator -------------------------------------------
    # The one account that may manage the others. Set SUPER_ADMIN_PASSWORD in
    # the environment; when it is missing the app generates a random password
    # at start-up and prints it once to the log, so an unconfigured deployment
    # is never reachable with a guessable default.
    SUPER_ADMIN_USER = os.environ.get("SUPER_ADMIN_USER", "superadmin")
    SUPER_ADMIN_PASSWORD = os.environ.get("SUPER_ADMIN_PASSWORD")

    # Session cookie. Secure is on by default because the app is served over
    # HTTPS on Render; set SESSION_COOKIE_SECURE=0 for plain-HTTP local runs.
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "1") != "0"
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 8  # 8 hours

    MAX_CONTENT_LENGTH = 8 * 1024 * 1024  # 8 MB upload ceiling
