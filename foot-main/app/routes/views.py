"""HTML views."""
from flask import Blueprint, render_template, request

from ..auth import current_user, require_auth
from ..services.teams import all_competitions, squad_meta, teams_for

bp = Blueprint("views", __name__)

# Ligue 2 pools: each is its own squad, background and badge, but shares the
# "ligue2" competition preset for the title and header logo.
POOLS = {
    "pool1": {"squad": "l2-pool1", "label": "المجموعة الأولى"},
    "pool2": {"squad": "l2-pool2", "label": "المجموعة الثانية"},
}

# The three standings tables the studio can build, each tied to a squad.
RANKINGS = [
    {"league": "ligue1", "label": "الرابطة 1",
     "subtitle": "بطولة الرابطة المحترفة 1"},
    {"league": "l2-pool1", "label": "الرابطة 2 — المجموعة 1",
     "subtitle": "بطولة الرابطة المحترفة 2 — المجموعة الأولى"},
    {"league": "l2-pool2", "label": "الرابطة 2 — المجموعة 2",
     "subtitle": "بطولة الرابطة المحترفة 2 — المجموعة الثانية"},
]


@bp.get("/")
def landing():
    """League chooser. Signed out, it is the sign-in page instead."""
    comps = {c["code"]: c for c in all_competitions()}
    leagues = [comps[c] for c in ("ligue1", "ligue2") if c in comps]
    return render_template("landing.html", leagues=leagues, pools=POOLS,
                           user=current_user())


@bp.get("/studio")
@require_auth
def studio():
    """The poster editor.

    ``?competition=`` preselects a competition; ``?pool=`` scopes Ligue 2 to
    one of its two pools (which also swaps the roster and background).
    """
    comps = all_competitions()
    codes = {c["code"] for c in comps}

    pool = request.args.get("pool", "")
    selected = request.args.get("competition", "ligue1")
    if selected not in codes:
        selected = "ligue1"

    if pool in POOLS:
        squad = POOLS[pool]["squad"]
        selected = "ligue2"
        pool_label = POOLS[pool]["label"]
    else:
        squad = "ligue1"
        pool_label = ""

    meta = squad_meta(squad)
    ctx = {"squad": squad, "pool": pool if pool in POOLS else "",
           "pool_label": pool_label, "background": meta["background"],
           "brand": meta["brand"]}

    return render_template("index.html", teams=teams_for(squad),
                           competitions=comps, selected=selected,
                           render_ctx=ctx, user=current_user())


@bp.get("/live")
@require_auth
def live():
    """Live Ligue 1 scoreboard (API-Football). Auto-refreshes on the client."""
    return render_template("live.html", teams=teams_for("ligue1"),
                           user=current_user())


@bp.get("/ranking")
@require_auth
def ranking():
    """Editable standings, one table per league / pool."""
    league = request.args.get("league", "ligue1")
    entry = next((r for r in RANKINGS if r["league"] == league), RANKINGS[0])
    meta = squad_meta(entry["league"])
    ctx = {"league": entry["league"], "subtitle": entry["subtitle"],
           "background": meta["background"], "brand": meta["brand"]}
    return render_template("ranking.html", rankings=RANKINGS, current=entry,
                           teams=teams_for(entry["league"]), rank_ctx=ctx,
                           user=current_user())
