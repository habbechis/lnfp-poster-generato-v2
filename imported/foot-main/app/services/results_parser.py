"""Parse a pasted results bulletin into matches and a standings table.

The league circulates round results as plain text, e.g.::

    Suite 15eme J RETOUR LIGUE 1

    CA 1 / OB 1   utilisations et jets de fumigenes
    USM 3 / ASS 0   RAS
    CSS 3 / ESS 1   jets d'objets

    CLASSEMENT
    CA   66
    EST  63
    ...

``parse()`` turns that into team codes, scores and standing rows so the studio
can fill a *Résultats* poster (and the ranking editor a table) in one paste.
It is deliberately forgiving: trailing commentary is ignored, separators may be
``/``, ``-`` or ``vs``, digits may be Arabic-Indic, and anything it cannot map
is reported in ``unknown`` rather than dropped silently.
"""
from __future__ import annotations

import re
import unicodedata

from .teams import SQUADS, teams_for

# Acronyms that appear in bulletins but differ from our ``short`` field.
_ALIASES = {
    "ESHS": ["HS", "ESHSOUSSE"],
    "CSHL": ["HL", "CSHLIF"],
    "JSO": ["JSOM", "JSEO"],
    "PSS": ["PSSAKIET", "SAKIET"],
    "ASM": ["ASMARSA"],
    "USBG": ["USBGUERDANE", "USB"],
    "ESZ": ["ESZARZIS"],
    "ESM": ["ESMETLAOUI"],
    "OB": ["OBEJA"],
    "CAB": ["CABIZERTIN"],
    "ST": ["STUNISIEN"],
}

# Arabic-Indic and Eastern-Arabic digits -> ASCII.
_DIGITS = {ord(c): str(i) for i, c in enumerate("٠١٢٣٤٥٦٧٨٩")}
_DIGITS.update({ord(c): str(i) for i, c in enumerate("۰۱۲۳۴۵۶۷۸۹")})

# "CA 1 / OB 1", "USM 3 - ASS 0", "CSS 3 vs ESS 1" (trailing text ignored).
_MATCH_RE = re.compile(
    r"^\s*([A-Za-z]{1,6})\s*[\.\-]?\s+(\d{1,2})\s*(?:/|-|vs\.?|–|—)\s*"
    r"([A-Za-z]{1,6})\s*[\.\-]?\s+(\d{1,2})(?!\d)",
    re.IGNORECASE)

# The other common layout: "EST 2 - 1 CA" (both scores in the middle).
_MATCH_MID_RE = re.compile(
    r"^\s*([A-Za-z]{1,6})\s+(\d{1,2})\s*(?:/|-|vs\.?|–|—|:)\s*(\d{1,2})\s+"
    r"([A-Za-z]{1,6})(?![A-Za-z])",
    re.IGNORECASE)

# "CA 66", "EST | 63", "1. CA 66" — one club, one total.
_STANDING_RE = re.compile(
    r"^\s*(?:\d{1,2}\s*[\.\)\-]\s*)?([A-Za-z]{1,6})\s*[\|\.\-:]?\s+(\d{1,3})"
    r"\s*(?:\|.*)?$")

_ROUND_RE = re.compile(
    # 15ème J / 15eme J / 15e J / 1ère J / 1er J / 2nd J
    r"(?:(\d{1,2})\s*(?:[eè](?:me|re)?|er|re|nd)?\s*[\.\)]?\s*J"
    r"|(?:الجولة|جولة)\s*(\d{1,2}))", re.I)             # الجولة 15
_CLASSEMENT_RE = re.compile(r"classement|ترتيب|الترتيب", re.I)

# Bulletin vocabulary that looks like an acronym but never names a club, so a
# header such as "LIGUE 1" is not mistaken for a standing row.
_NOT_CLUB = {"LIGUE", "L", "J", "JOURNEE", "SUITE", "RETOUR", "ALLER", "RAS",
             "POULE", "GROUPE", "GROUPE1", "GROUPE2", "CLASSEMENT", "MATCH",
             "MATCHS", "TOTAL", "PTS", "POINTS", "PT", "EQUIPE", "EQUIPES",
             "CLUB", "CLUBS", "RESULTATS", "RESULTAT", "DIV", "PLAY", "OFF"}


def _ascii_digits(text: str) -> str:
    return (text or "").translate(_DIGITS)


def _key(value: str) -> str:
    """Normalise an acronym: strip accents/punctuation, upper-case."""
    v = unicodedata.normalize("NFKD", value or "")
    v = "".join(c for c in v if not unicodedata.combining(c))
    return re.sub(r"[^A-Za-z]", "", v).upper()


def _lookup(squad: str) -> tuple[dict, dict]:
    """Return (home_table, other_table) of acronym -> team code.

    ``home_table`` is the squad being edited and always wins, so shared
    acronyms never resolve to the wrong league. ``other_table`` covers the
    remaining squads: a bulletin can name a club that sits in another league
    (relegated since, or a cup tie), and every club carries its own crest and
    logo directory, so such a match still renders correctly. Callers report
    those separately instead of silently mixing leagues.
    """
    def build(name):
        table: dict[str, str] = {}
        for t in teams_for(name):
            code = t["code"]
            keys = [t.get("short", ""), code]
            keys += _ALIASES.get(_key(t.get("short", "")), [])
            for k in keys:
                k = _key(k)
                if k:
                    table[k] = code
        return table

    squad = squad if squad in SQUADS else "ligue1"
    home = build(squad)
    other: dict[str, str] = {}
    for name in SQUADS:
        if name == squad:
            continue
        for k, code in build(name).items():
            other.setdefault(k, code)
    return home, other


def parse(text: str, squad: str = "ligue1") -> dict:
    """Extract matches and standings from a pasted bulletin."""
    text = _ascii_digits(text or "")
    table, other = _lookup(squad)
    matches, standings, unknown, foreign = [], [], [], []
    seen_unknown, seen_standing, seen_foreign = set(), set(), set()
    # When the bulletin marks its table, only read standings below that marker —
    # that keeps headers like "LIGUE 1" out of the table.
    gated = bool(_CLASSEMENT_RE.search(text))
    in_classement = False
    round_no = None
    leg = None

    def note_unknown(label):
        k = _key(label)
        if k and k not in _NOT_CLUB and k not in seen_unknown:
            seen_unknown.add(k)
            unknown.append(label.upper())

    def note_foreign(label):
        k = _key(label)
        if k not in seen_foreign:
            seen_foreign.add(k)
            foreign.append(label.upper())

    def resolve(label):
        """Active squad first, then any other league (reported as foreign)."""
        k = _key(label)
        if k in table:
            return table[k]
        if k in other:
            note_foreign(label)
            return other[k]
        note_unknown(label)
        return None

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue

        low = line.lower()
        if _CLASSEMENT_RE.search(line):
            in_classement = True
            continue
        if round_no is None:
            m = _ROUND_RE.search(line)
            # Only trust a round number on a header line, never on a result.
            if m and not _MATCH_RE.match(line) and not _MATCH_MID_RE.match(line):
                round_no = int(m.group(1) or m.group(2))
        if leg is None:
            if "retour" in low or "إياب" in line:
                leg = "retour"
            elif "aller" in low or "ذهاب" in line:
                leg = "aller"

        # A result line always wins over a standing line (it has two clubs).
        m = _MATCH_RE.match(line)
        if m:
            ha, hs, aa, as_ = m.group(1), m.group(2), m.group(3), m.group(4)
        else:                                   # "EST 2 - 1 CA" layout
            m = _MATCH_MID_RE.match(line)
            if m:
                ha, hs, as_, aa = (m.group(1), m.group(2),
                                   m.group(3), m.group(4))
        if m and not in_classement:
            home, away = resolve(ha), resolve(aa)
            matches.append({
                "home": home, "away": away,
                "home_label": ha.upper(), "away_label": aa.upper(),
                "score_home": int(hs), "score_away": int(as_),
            })
            continue

        s = _STANDING_RE.match(line) if (in_classement or not gated) else None
        if s:
            acr, pts = s.group(1), s.group(2)
            k = _key(acr)
            if k in _NOT_CLUB:
                continue
            code = table.get(k)
            if code is None:
                # A table belongs to one league: a club from another one has no
                # row to fill here, so flag it rather than inventing a row.
                note_foreign(acr) if k in other else note_unknown(acr)
                continue
            if code in seen_standing:
                continue
            seen_standing.add(code)
            standings.append({"code": code, "points": int(pts),
                              "label": acr.upper()})

    return {
        "round": round_no,
        "leg": leg,
        "matchday": _matchday(round_no, leg, squad),
        "title_ar": _title(round_no, leg),
        "matches": matches,
        "standings": standings,
        "unknown": unknown,
        "foreign": foreign,
    }


def _matchday(round_no, leg, squad) -> int | None:
    """Games played by each club after this round — what the table's "لعب"
    column holds.

    A round number is counted inside its leg: "15ème J RETOUR" is the 15th
    round of the second half, so every club has already played a full first
    leg (teams - 1 rounds) on top of it. Getting this wrong is visible in the
    data — 66 points cannot happen in 15 games.
    """
    if not round_no:
        return None
    if leg != "retour":
        return round_no
    try:
        per_leg = len(teams_for(squad if squad in SQUADS else "ligue1")) - 1
    except Exception:
        return round_no
    return per_leg + round_no


def _title(round_no, leg) -> str:
    """An Arabic results heading for the parsed round, for the manual title."""
    if not round_no:
        return "نتائج مباريات\nاليوم"
    suffix = {"retour": " إياب", "aller": " ذهاب"}.get(leg or "", "")
    return f"نتائج مباريات\nالجولة {round_no}{suffix}"
