"""Parse an LNFP fixtures bulletin (تعيينات) into scheduled matches.

The federation publishes the round as a table grouped by day::

    السبت 22 أوت 2026
    الهادي النيفر باردو   س16و30د   الملعب التونسي/النادي الرياضي الصفاقسي
    ــــــــ              س16و30د   الأمل الرياضي بحمام سوسة/الإتحاد الرياضي المنستيري

    الأحد 23 أوت 2026
    حمادي العقربي برادس   س16و30د   الترجي الرياضي التونسي/النجم الرياضي الساحلي

Each row carries a stadium, a kick-off time and the two clubs separated by
``/``; a row of dashes means the ground is not fixed yet, and stays empty.

Matching Arabic club names is the hard part: the bulletin and our roster
disagree on spelling (بحمام vs لحمام, ببنقردان vs ببن قردان, بالعمران vs
العمرانية, إفريقي vs أفريقي). Names are therefore normalised, compared without
spaces, and finally scored on stemmed tokens, so those variants still resolve.
"""
from __future__ import annotations

import re
import unicodedata

from .dates import _MONTHS
from .teams import SQUADS, teams_for

# Arabic-Indic digits -> ASCII.
_DIGITS = {ord(c): str(i) for i, c in enumerate("٠١٢٣٤٥٦٧٨٩")}
_DIGITS.update({ord(c): str(i) for i, c in enumerate("۰۱۲۳۴۵۶۷۸۹")})

_TATWEEL = "ـ"
_DIACRITICS = re.compile(r"[ً-ْٰۖ-ۭ]")

# Words shared by most club names, so they carry no identifying weight.
_STOP_STEMS = {"نادي", "رياض", "رياضه", "جمعيه", "اتحاد", "ترج", "نجم",
               "امل", "مستقبل", "تقدم", "شبيبه", "ملعب", "اولمب"}

_MONTHS_RE = "|".join(re.escape(m) for m in _MONTHS.values())
_MONTH_NUM = {v: k for k, v in _MONTHS.items()}
# "السبت 22 أوت 2026" / "22أوت2026"
_DATE_RE = re.compile(rf"(\d{{1,2}})\s*({_MONTHS_RE})\s*(\d{{4}})")
# "س16و30د" / "16:30" / "16h30"
_TIME_RE = re.compile(r"(?:س\s*)?(\d{1,2})\s*(?:و|:|h|H)\s*(\d{2})\s*(?:د)?")
# A run of dashes/underscores stands for "not fixed yet".
_DASHES = re.compile(r"^[\s\-‐-―_\.؟]*$")


def _norm(text: str) -> str:
    """Normalise Arabic for comparison: no diacritics, unified letter forms."""
    t = unicodedata.normalize("NFKC", text or "").replace(_TATWEEL, "")
    t = _DIACRITICS.sub("", t)
    for src, dst in (("أإآٱ", "ا"), ("ة", "ه"), ("ى", "ي"), ("ؤ", "و"),
                     ("ئ", "ي")):
        for ch in src:
            t = t.replace(ch, dst)
    return " ".join(t.split())


def _flat(text: str) -> str:
    """Normalised with every space removed — beats spacing disagreements."""
    return _norm(text).replace(" ", "")


def _stem(token: str) -> str:
    """Crude Arabic stem: drop clitic prefixes and feminine/plural endings."""
    t = token
    for p in ("بال", "وال", "فال", "كال", "لل", "ال", "ب", "ل", "ك", "ف", "و"):
        if t.startswith(p) and len(t) - len(p) >= 3:
            t = t[len(p):]
            break
    for s in ("يه", "ات", "ين", "ون", "ه", "ي"):
        if t.endswith(s) and len(t) - len(s) >= 3:
            t = t[:-len(s)]
            break
    return t


def _stems(text: str) -> set[str]:
    toks = {_stem(t) for t in _norm(text).split() if len(t) > 1}
    meaningful = {t for t in toks if t not in _STOP_STEMS}
    return meaningful or toks


def _roster(squad: str) -> list[dict]:
    squad = squad if squad in SQUADS else "ligue1"
    out = []
    for t in teams_for(squad):
        out.append({"code": t["code"], "name_ar": t.get("name_ar", ""),
                    "flat": _flat(t.get("name_ar", "")),
                    "stems": _stems(t.get("name_ar", ""))})
    return out


def _score(candidate: str, team: dict) -> float:
    """How strongly ``candidate`` names ``team`` (0 = not at all, 1 = exact)."""
    cf = _flat(candidate)
    if not cf or not team["flat"]:
        return 0.0
    if cf == team["flat"]:
        return 1.0
    # One contains the other: the bulletin often adds or drops a word.
    if cf in team["flat"] or team["flat"] in cf:
        shorter, longer = sorted((len(cf), len(team["flat"])))
        return 0.9 * shorter / longer
    cs = _stems(candidate)
    if not cs:
        return 0.0
    inter = len(cs & team["stems"])
    if not inter:
        return 0.0
    return 0.8 * inter / len(cs | team["stems"])


def _best(candidate: str, roster: list[dict]) -> tuple[dict | None, float]:
    best, score = None, 0.0
    for t in roster:
        s = _score(candidate, t)
        if s > score:
            best, score = t, s
    return best, score


def _split_team(tokens: list[str], roster: list[dict], from_end: bool):
    """Find the club inside a run of words and return (team, leftover words).

    The bulletin packs the stadium and a club into one cell, so the club is
    taken as the best-scoring run of words at one end and whatever is left over
    is the stadium.
    """
    if not tokens:
        return None, [], 0.0
    best = (None, tokens, 0.0)
    for k in range(1, len(tokens) + 1):
        part = tokens[-k:] if from_end else tokens[:k]
        rest = tokens[:-k] if from_end else tokens[k:]
        team, score = _best(" ".join(part), roster)
        if team and score > best[2]:
            best = (team, rest, score)
    return best


def _clean_stadium(words: list[str]) -> str:
    text = " ".join(words).strip()
    if not text or _DASHES.match(text):
        return ""
    # Strip a leading/trailing dash run left over from an empty cell.
    return re.sub(r"^[\-‐-―_\s]+|[\-‐-―_\s]+$", "", text)


def parse(text: str, squad: str = "ligue1", threshold: float = 0.34) -> dict:
    """Extract the scheduled matches, grouped by match day."""
    text = (text or "").translate(_DIGITS)
    roster = _roster(squad)
    days: list[dict] = []
    current: dict | None = None
    unknown: list[str] = []

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue

        d = _DATE_RE.search(line)
        if d and "/" not in line:
            day, month, year = int(d.group(1)), _MONTH_NUM[d.group(2)], int(d.group(3))
            current = {"date_iso": f"{year:04d}-{month:02d}-{day:02d}",
                       "date_label": line, "matches": []}
            days.append(current)
            continue

        if "/" not in line:
            continue

        # Pull the kick-off time out first; what remains is stadium + clubs.
        time = ""
        m = _TIME_RE.search(line)
        if m:
            hh, mm = int(m.group(1)), int(m.group(2))
            if hh < 24 and mm < 60:
                time = f"{hh:02d}:{mm:02d}"
                line = (line[:m.start()] + " " + line[m.end():]).strip()

        left, _, right = line.partition("/")
        home, left_rest, hs = _split_team(left.split(), roster, from_end=True)
        away, right_rest, as_ = _split_team(right.split(), roster, from_end=False)
        if hs < threshold:
            home = None
        if as_ < threshold:
            away = None
        for part, team in ((left, home), (right, away)):
            if team is None:
                label = " ".join(part.split()[:4])
                if label and label not in unknown:
                    unknown.append(label)

        # The stadium sits on whichever side is not the club.
        stadium = _clean_stadium(left_rest) or _clean_stadium(right_rest)
        if current is None:
            current = {"date_iso": "", "date_label": "", "matches": []}
            days.append(current)
        current["matches"].append({
            "home": home["code"] if home else None,
            "away": away["code"] if away else None,
            "home_name": home["name_ar"] if home else "",
            "away_name": away["name_ar"] if away else "",
            "time": time or "16:30",
            "stadium_ar": stadium,
        })

    days = [d for d in days if d["matches"]]
    return {"days": days,
            "match_count": sum(len(d["matches"]) for d in days),
            "unknown": unknown}


# --------------------------------------------------------------------------- #
# PDF input
# --------------------------------------------------------------------------- #
_ARABIC = re.compile(r"[؀-ۿ]")


def text_from_pdf(stream) -> tuple[str, str | None]:
    """Pull the text layer out of a fixtures PDF. Returns (text, error).

    Only *digital* PDFs carry real text. A scanned bulletin either has no text
    layer at all, or one produced by an OCR pass that mangles Arabic into Latin
    look-alikes — in both cases the club names cannot be recovered, so say so
    plainly instead of returning nonsense.
    """
    try:
        from pypdf import PdfReader
    except Exception as exc:  # pragma: no cover - dependency missing
        return "", f"pypdf غير متوفّر: {exc}"
    try:
        reader = PdfReader(stream)
        text = "\n".join((p.extract_text() or "") for p in reader.pages)
    except Exception as exc:
        return "", f"تعذّر قراءة ملف PDF: {exc}"
    if not _ARABIC.search(text):
        return text, ("هذا الملف صورة ممسوحة ضوئياً (لا يحتوي نصاً عربياً "
                      "قابلاً للقراءة) — انسخ النص والصقه في الخانة بدلاً منه.")
    return text, None
