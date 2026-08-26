"""Team registry — loaded once from ``data/teams.json``."""
from __future__ import annotations

import json
import os
from functools import lru_cache

_DATADIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "data")
_DATA = os.path.join(_DATADIR, "teams.json")

# A squad is one selectable roster. Ligue 1 is the whole league; Ligue 2 is
# split into two pools, each with its own crest set, background and title.
SQUADS = {
    "ligue1":   {"file": "teams.json",           "logos": "logos",
                 "background": "bg-vide.png",   "brand": "logo-ligue1.png"},
    "l2-pool1": {"file": "teams-l2-pool1.json",  "logos": "logos-l2",
                 "background": "bg-ligue2.png", "brand": "logo-ligue2.png"},
    "l2-pool2": {"file": "teams-l2-pool2.json",  "logos": "logos-l2",
                 "background": "bg-ligue2.png", "brand": "logo-ligue2.png"},
}
DEFAULT_SQUAD = "ligue1"


_COMPS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "data", "competitions.json")
_CHANNELS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "data", "channels.json")


@lru_cache(maxsize=8)
def teams_for(squad: str) -> list[dict]:
    """The roster for one squad, each team tagged with its logo directory."""
    spec = SQUADS.get(squad) or SQUADS[DEFAULT_SQUAD]
    with open(os.path.join(_DATADIR, spec["file"]), encoding="utf-8") as fh:
        teams = json.load(fh)["teams"]
    return [{**t, "_logos": spec["logos"]} for t in teams]


def all_teams() -> list[dict]:
    return teams_for(DEFAULT_SQUAD)


def squad_meta(squad: str) -> dict:
    return SQUADS.get(squad) or SQUADS[DEFAULT_SQUAD]


@lru_cache(maxsize=1)
def all_competitions() -> list[dict]:
    """Competition presets: each supplies a default title and header badge."""
    with open(_COMPS, encoding="utf-8") as fh:
        return json.load(fh)["competitions"]


@lru_cache(maxsize=1)
def _by_code() -> dict[str, dict]:
    """Every team across every squad, keyed by its globally-unique code."""
    out = {}
    for squad in SQUADS:
        for t in teams_for(squad):
            out[t["code"]] = t
    return out


def get_team(code: str) -> dict | None:
    return _by_code().get(code)


def team_side(code: str) -> dict:
    """Compact team payload used inside a match record."""
    t = get_team(code) or {}
    return {
        "code": code,
        "name_ar": t.get("name_ar", ""),
        "name_fr": t.get("name_fr", ""),
        "logo": t.get("logo", ""),
        # Which static folder the crest lives in, so the renderer can find it.
        "logo_dir": t.get("_logos", "logos"),
    }


@lru_cache(maxsize=1)
def _channels_doc() -> dict:
    with open(_CHANNELS, encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache(maxsize=1)
def all_channels() -> list[dict]:
    """Broadcasters that can be shown under a fixture's ground."""
    return _channels_doc()["channels"]


@lru_cache(maxsize=1)
def max_channels_per_match() -> int:
    # Every registered broadcaster may be picked: the row can carry them all.
    return len(all_channels())


@lru_cache(maxsize=1)
def _channel_by_code() -> dict[str, dict]:
    return {c["code"]: c for c in all_channels()}


def channel_logos(codes) -> list[str]:
    """Map selected codes to logo file names, in registry order, capped."""
    wanted = {c for c in (codes or []) if isinstance(c, str)}
    logos = [c["logo"] for c in all_channels() if c["code"] in wanted]
    return logos[:max_channels_per_match()]


# Ready-made banners that combine several broadcaster logos into one artwork
# (from the "logoTVcomibined" set). When the picked channels match a set
# exactly, the banner is preferred over laying the logos out one by one.
_COMBINED_CHANNELS = {
    frozenset({"diwansport", "wataniasport"}): "diwan_wataniasport.png",
    frozenset({"elkess", "diwansport"}): "elkess_diwan.png",
    frozenset({"watania1", "elkess"}): "watania1_elkess.png",
    frozenset({"watania1", "diwansport"}): "watania1_diwan.png",
    frozenset({"watania1", "diwansport", "elkess"}): "watania1_diwan_elkess.png",
    frozenset({"watania2", "diwansport"}): "watania2_diwan.png",
    frozenset({"watania2", "diwansport", "elkess"}): "watania2_diwan_elkess.png",
}


def combined_channel_logo(codes) -> str | None:
    """The ready banner for the exact set of picked channels, or None."""
    wanted = frozenset(c for c in (codes or []) if isinstance(c, str))
    return _COMBINED_CHANNELS.get(wanted)
