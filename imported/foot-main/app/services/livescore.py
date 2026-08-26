"""Live scoring with a pluggable provider.

Two providers, one normalised shape:

* **TheSportsDB** (default, free) — no key needed (public key "3"), covers the
  *current* Tunisian Ligue 1 season for results and the league table. Real-time
  in-play is Patreon-only there, so scores appear once matches finish — which is
  what a poster/standings tool needs.
* **API-Football** — optional upgrade for true in-play scores; needs a key, and
  its free plan is limited to past seasons.

``Config.LIVE_PROVIDER`` picks one ("auto" uses API-Football when a key is set,
otherwise TheSportsDB). Every public function returns a plain dict/list and
never raises into a request handler; responses are cached in-process so polling
never drains a provider's quota.
"""
from __future__ import annotations

import json
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import date

from .teams import teams_for

_UA = "LNFP-Affiches/1.0 (+https://foot-duci.onrender.com)"

# Extra spellings a provider may use, keyed by our team code. Matching also
# falls back to the normalised French name, so this only lists the tricky ones.
_ALIASES = {
    "est": ["esperance tunis", "es tunis", "esperance de tunis",
            "esperance sportive de tunis"],
    "ca": ["club africain"],
    "css": ["cs sfaxien", "club sfaxien", "sfax"],
    "ess": ["etoile sahel", "etoile du sahel", "etoile sportive du sahel"],
    "st": ["stade tunisien"],
    "cab": ["ca bizertin", "bizertin", "bizerte"],
    "usm": ["us monastir", "monastir"],
    "usbg": ["us ben guerdane", "ben guerdane"],
    "esz": ["es zarzis", "zarzis"],
    "esm": ["es metlaoui", "metlaoui"],
    "asm": ["as marsa", "la marsa", "marsa"],
    "ob": ["olympique beja", "o beja", "beja"],
    "cshl": ["cs hammam-lif", "hammam lif", "hammam-lif"],
    "eshs": ["es hammam sousse", "hammam sousse"],
    "jso": ["js el omrane", "el omrane", "omrane"],
    "pss": ["ps sakiet", "sakiet", "sakiet eddaier", "progres sakiet"],
}

# Tokens that carry no identifying weight when matching club names.
_STOP = {"es", "us", "cs", "ca", "as", "sc", "js", "ps", "o", "of",
         "club", "sportif", "sportive", "athletique", "olympique", "union",
         "avenir", "espoir", "esperance", "etoile", "stade", "jeunesse",
         "progres", "de", "du", "la", "le", "el", "fc"}

_lock = threading.Lock()
_cache: dict[str, tuple[float, object]] = {}
# Last-seen daily quota, read from a provider's response headers (API-Football).
_quota: dict = {"limit": None, "remaining": None, "at": None}


# --------------------------------------------------------------------------- #
# Name matching
# --------------------------------------------------------------------------- #
def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower().replace("-", " ").replace(".", " ").replace("'", " ")
    return " ".join(ch for ch in text.split() if ch)


def _tokens(text: str) -> set[str]:
    return {t for t in _norm(text).split() if t not in _STOP} or set(
        _norm(text).split())


def _index():
    idx = _cache.get("_name_index")
    if idx:
        return idx
    exact, tokenised = {}, {}
    for t in teams_for("ligue1"):
        code = t["code"]
        keys = [t.get("name_fr", ""), t.get("short", ""), code]
        keys += _ALIASES.get(code, [])
        for k in keys:
            n = _norm(k)
            if n:
                exact[n] = code
        tokenised[code] = _tokens(t.get("name_fr", "") + " " +
                                  " ".join(_ALIASES.get(code, [])))
    idx = (exact, tokenised)
    _cache["_name_index"] = idx
    return idx


def resolve_code(api_name: str) -> str | None:
    """Best-effort map a provider's club name to our team code."""
    exact, tokenised = _index()
    n = _norm(api_name)
    if n in exact:
        return exact[n]
    want = _tokens(api_name)
    best, best_score = None, 0.0
    for code, toks in tokenised.items():
        if not toks:
            continue
        overlap = len(want & toks)
        if not overlap:
            continue
        score = overlap / max(1, len(want | toks))
        if score > best_score:
            best, best_score = code, score
    return best if best_score >= 0.34 else None


# --------------------------------------------------------------------------- #
# Provider selection + shared HTTP/cache
# --------------------------------------------------------------------------- #
def _provider(config) -> str:
    p = (getattr(config, "LIVE_PROVIDER", "auto") or "auto").lower()
    if p in ("apifootball", "thesportsdb"):
        return p
    return "apifootball" if getattr(config, "APIFOOTBALL_KEY", None) \
        else "thesportsdb"


def configured(config) -> bool:
    """True when the active provider can serve data at all."""
    if _provider(config) == "thesportsdb":
        return bool(getattr(config, "THESPORTSDB_KEY", None))  # default "3"
    return bool(getattr(config, "APIFOOTBALL_KEY", None))


def _start_year(config) -> int:
    s = (getattr(config, "APIFOOTBALL_SEASON", "") or "").strip()
    if s.isdigit():
        return int(s)
    today = date.today()
    return today.year if today.month >= 7 else today.year - 1


def _http_json(url, headers, ttl, cache_key):
    """GET + cache any JSON endpoint. Returns (data, error)."""
    now = time.time()
    with _lock:
        hit = _cache.get(cache_key)
        if hit and now - hit[0] < ttl:
            return hit[1], None
    req = urllib.request.Request(url, headers={
        **headers, "Accept": "application/json", "User-Agent": _UA})
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            _read_quota(resp.headers)
            data = json.loads(resp.read() or "{}")
    except urllib.error.HTTPError as exc:
        return None, _http_error(exc)
    except Exception as exc:  # network / JSON / timeout
        return None, str(exc)
    with _lock:
        _cache[cache_key] = (now, data)
    return data, None


def _http_error(exc) -> str:
    detail = ""
    try:
        body = json.loads(exc.read() or "{}")
        msg = body.get("message") or body.get("errors")
        if isinstance(msg, dict):
            msg = "; ".join(f"{k}: {v}" for k, v in msg.items())
        detail = f" — {msg}" if msg else ""
    except Exception:
        pass
    if exc.code == 403 and not detail:
        detail = " — clé refusée (vérifiez la clé API)"
    return f"HTTP {exc.code}{detail}"


def _read_quota(headers) -> None:
    try:
        limit = headers.get("x-ratelimit-requests-limit")
        remaining = headers.get("x-ratelimit-requests-remaining")
    except Exception:
        return
    if limit is None and remaining is None:
        return
    with _lock:
        _quota["limit"] = int(limit) if limit and str(limit).isdigit() else limit
        _quota["remaining"] = (int(remaining) if remaining
                               and str(remaining).isdigit() else remaining)
        _quota["at"] = time.time()


def quota() -> dict:
    with _lock:
        return dict(_quota)


def _int_or_none(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------- #
# API-Football provider
# --------------------------------------------------------------------------- #
_AF_LIVE = {"1H", "HT", "2H", "ET", "BT", "P", "LIVE", "INT"}


def _af_get(config, path, params, ttl):
    key = "af:" + path + "?" + urllib.parse.urlencode(sorted(params.items()))
    url = f"{config.APIFOOTBALL_BASE_URL.rstrip('/')}/{path}?" \
          f"{urllib.parse.urlencode(params)}"
    data, err = _http_json(url, {"x-apisports-key": config.APIFOOTBALL_KEY},
                           ttl, key)
    if err:
        return None, err
    errs = (data or {}).get("errors")
    if errs:
        msg = "; ".join(f"{k}: {v}" for k, v in errs.items()) if isinstance(
            errs, dict) else str(errs)
        if msg:
            # A rules/season problem is not fatal to the app — report it.
            with _lock:
                _cache.pop(key, None)
            return None, msg
    return data, None


def _af_row(fx):
    teams = fx.get("teams", {})
    goals = fx.get("goals", {})
    st = (fx.get("fixture", {}).get("status", {}) or {})
    hn = (teams.get("home", {}) or {}).get("name", "")
    an = (teams.get("away", {}) or {}).get("name", "")
    return {
        "home": resolve_code(hn), "away": resolve_code(an),
        "home_name": hn, "away_name": an,
        "home_logo": (teams.get("home", {}) or {}).get("logo", ""),
        "away_logo": (teams.get("away", {}) or {}).get("logo", ""),
        "score_home": goals.get("home"), "score_away": goals.get("away"),
        "status": st.get("short", ""), "status_long": st.get("long", ""),
        "elapsed": st.get("elapsed"),
        "live": st.get("short") in _AF_LIVE,
        "finished": st.get("short") in {"FT", "AET", "PEN"},
        "timestamp": fx.get("fixture", {}).get("timestamp"),
        "date": (fx.get("fixture", {}).get("date") or "")[:10],
    }


def _af_fixtures(config, params, ttl):
    data, err = _af_get(config, "fixtures", params, ttl)
    if err:
        return None, err
    rows = [_af_row(fx) for fx in (data or {}).get("response", [])]
    rows.sort(key=lambda r: r.get("timestamp") or 0)
    return rows, None


def _af_live(config):
    return _af_fixtures(config, {"league": config.APIFOOTBALL_LEAGUE_ID,
                                 "season": _start_year(config), "live": "all"},
                        config.APIFOOTBALL_LIVE_TTL)


def _af_on(config, day):
    return _af_fixtures(config, {"league": config.APIFOOTBALL_LEAGUE_ID,
                                 "season": _start_year(config), "date": day},
                        config.APIFOOTBALL_STATIC_TTL)


def _af_standings(config):
    data, err = _af_get(config, "standings",
                        {"league": config.APIFOOTBALL_LEAGUE_ID,
                         "season": _start_year(config)},
                        config.APIFOOTBALL_STATIC_TTL)
    if err:
        return None, err
    try:
        tables = (data or {})["response"][0]["league"]["standings"]
        table = tables[0] if tables and isinstance(tables[0], list) else tables
    except (IndexError, KeyError, TypeError):
        table = []
    rows = []
    for e in table or []:
        code = resolve_code((e.get("team", {}) or {}).get("name", ""))
        if not code:
            continue
        rows.append({"code": code, "rank": e.get("rank"),
                     "points": e.get("points") or 0,
                     "played": (e.get("all", {}) or {}).get("played") or 0})
    return rows, None


# --------------------------------------------------------------------------- #
# TheSportsDB provider (free, current season)
# --------------------------------------------------------------------------- #
_TSDB_FINISHED = {"match finished", "ft", "aet", "after extra time",
                  "pen", "final", "finished"}


def _tsdb_season(config) -> str:
    y = _start_year(config)
    return f"{y}-{y + 1}"


def _tsdb_url(config, path) -> str:
    base = config.THESPORTSDB_BASE_URL.rstrip("/")
    return f"{base}/api/v1/json/{config.THESPORTSDB_KEY}/{path}"


def _tsdb_row(ev):
    hn = ev.get("strHomeTeam", "") or ""
    an = ev.get("strAwayTeam", "") or ""
    sh = _int_or_none(ev.get("intHomeScore"))
    sa = _int_or_none(ev.get("intAwayScore"))
    status = (ev.get("strStatus") or ev.get("strProgress") or "").strip()
    finished = status.lower() in _TSDB_FINISHED or (
        status in ("", "Match Finished") and sh is not None and sa is not None)
    ts = ev.get("strTimestamp") or ""
    return {
        "home": resolve_code(hn), "away": resolve_code(an),
        "home_name": hn, "away_name": an,
        "home_logo": ev.get("strHomeTeamBadge", "") or "",
        "away_logo": ev.get("strAwayTeamBadge", "") or "",
        "score_home": sh, "score_away": sa,
        "status": status, "status_long": status, "elapsed": None,
        "live": False,          # in-play is Patreon-only on TheSportsDB
        "finished": finished,
        "timestamp": ts, "date": ev.get("dateEvent") or "",
        "round": ev.get("intRound"),
    }


def _tsdb_season_events(config):
    """All events for the season — cached; both the board and the poster
    auto-fill filter this one list, so a matchday costs a single request."""
    path = f"eventsseason.php?id={config.THESPORTSDB_LEAGUE_ID}" \
           f"&s={_tsdb_season(config)}"
    data, err = _http_json(_tsdb_url(config, path), {},
                           config.APIFOOTBALL_STATIC_TTL, "tsdb:" + path)
    if err:
        return None, err
    events = (data or {}).get("events") or []
    rows = [_tsdb_row(e) for e in events]
    rows.sort(key=lambda r: r.get("timestamp") or r.get("date") or "")
    return rows, None


def _tsdb_live(config):
    """Show the whole current round, not just today — a Ligue 1 round is spread
    over several days, so filtering by today would drop half the matches."""
    rows, err = _tsdb_season_events(config)
    if err:
        return None, err
    if not rows:
        return [], None
    today = date.today().isoformat()

    # Group events by round and order rounds by their earliest date.
    by_round: dict = {}
    for r in rows:
        by_round.setdefault(r.get("round"), []).append(r)

    def start(items):
        dates = [i.get("date") for i in items if i.get("date")]
        return min(dates) if dates else ""

    ordered = sorted(by_round.values(), key=start)
    # The round that spans today, else the most recent one that has started,
    # else the next upcoming one.
    spanning = [g for g in ordered
                if start(g) <= today <= max((i.get("date") or "") for i in g)]
    if spanning:
        chosen = spanning[-1]
    else:
        started = [g for g in ordered if start(g) <= today]
        chosen = started[-1] if started else ordered[0]
    chosen.sort(key=lambda r: r.get("timestamp") or r.get("date") or "")
    return chosen, None


def _tsdb_on(config, day):
    rows, err = _tsdb_season_events(config)
    if err:
        return None, err
    return [r for r in rows if r.get("date") == day], None


def _tsdb_standings(config):
    path = f"lookuptable.php?l={config.THESPORTSDB_LEAGUE_ID}" \
           f"&s={_tsdb_season(config)}"
    data, err = _http_json(_tsdb_url(config, path), {},
                           config.APIFOOTBALL_STATIC_TTL, "tsdb:" + path)
    if err:
        return None, err
    rows = []
    for e in (data or {}).get("table") or []:
        code = resolve_code(e.get("strTeam", "") or e.get("name", ""))
        if not code:
            continue
        rows.append({"code": code, "rank": _int_or_none(e.get("intRank")),
                     "points": _int_or_none(e.get("intPoints")) or 0,
                     "played": _int_or_none(e.get("intPlayed")) or 0})
    return rows, None


# --------------------------------------------------------------------------- #
# Public API (dispatches to the active provider)
# --------------------------------------------------------------------------- #
def status(config) -> dict:
    prov = _provider(config)
    return {"configured": configured(config), "provider": prov,
            "season": _tsdb_season(config) if prov == "thesportsdb"
            else _start_year(config), "quota": quota()}


def live(config) -> dict:
    if not configured(config):
        return {"configured": False, "matches": []}
    prov = _provider(config)
    rows, err = _af_live(config) if prov == "apifootball" else _tsdb_live(config)
    if err:
        return {"configured": True, "provider": prov, "matches": [],
                "error": err, "quota": quota()}
    return {"configured": True, "provider": prov, "matches": rows,
            "quota": quota(), "live_count": sum(1 for r in rows if r["live"])}


def fixtures_on(config, day_iso: str) -> dict:
    if not configured(config):
        return {"configured": False, "matches": []}
    day = (day_iso or "").strip() or date.today().isoformat()
    prov = _provider(config)
    rows, err = _af_on(config, day) if prov == "apifootball" \
        else _tsdb_on(config, day)
    if err:
        return {"configured": True, "provider": prov, "matches": [],
                "error": err, "quota": quota()}
    return {"configured": True, "provider": prov, "date": day,
            "matches": rows, "quota": quota()}


def standings(config) -> dict:
    if not configured(config):
        return {"configured": False, "rows": []}
    prov = _provider(config)
    rows, err = _af_standings(config) if prov == "apifootball" \
        else _tsdb_standings(config)
    if err:
        return {"configured": True, "provider": prov, "rows": [],
                "error": err, "quota": quota()}
    return {"configured": True, "provider": prov, "rows": rows,
            "quota": quota()}
