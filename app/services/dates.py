"""Arabic (Tunisian) date formatting for the poster date bar."""
from __future__ import annotations

from datetime import date, datetime

# Sunday-first is not needed; datetime.weekday(): Monday=0 .. Sunday=6
_WEEKDAYS = {
    0: "الإثنين", 1: "الثلاثاء", 2: "الأربعاء", 3: "الخميس",
    4: "الجمعة", 5: "السبت", 6: "الأحد",
}
# Tunisian month names (French-derived, as used on official LNFP posters)
_MONTHS = {
    1: "جانفي", 2: "فيفري", 3: "مارس", 4: "أفريل", 5: "ماي", 6: "جوان",
    7: "جويلية", 8: "أوت", 9: "سبتمبر", 10: "أكتوبر", 11: "نوفمبر", 12: "ديسمبر",
}


def parse_iso(value: str) -> date | None:
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except (ValueError, AttributeError):
            continue
    return None


def arabic_date_label(value: str) -> str:
    """Turn an ISO date into e.g. ``الأحد 23 أوت 2026``.

    Falls back to the raw value if it cannot be parsed, so a caller may also
    pass an already-formatted label straight through.
    """
    d = parse_iso(value) if value else None
    if not d:
        return value or ""
    return f"{_WEEKDAYS[d.weekday()]} {d.day} {_MONTHS[d.month]} {d.year}"
