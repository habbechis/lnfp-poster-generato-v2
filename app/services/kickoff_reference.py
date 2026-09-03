"""Reference-driven KICK OFF renderer.

The visual structure intentionally follows the supplied reference poster:
one rounded white card per date, with the date ribbon overlapping the card,
and one or more match rows inside that card. The existing API/data model is
unchanged.
"""
from __future__ import annotations

import base64
import io
import os

from PIL import Image, ImageDraw, ImageFilter

from . import poster as _p

W, H = _p.W, _p.H
WHITE = (255, 255, 255, 255)
TEXT = (28, 28, 36, 255)
RED = (181, 10, 16, 255)
RED_DARK = (118, 5, 10, 255)
RED_GLOW = (225, 24, 30, 100)
REFERENCE_BG_B64_PATH = os.path.join(_p.STATIC, "img", "bg-kickoff-reference.b64")


def _load_reference_background():
    with open(REFERENCE_BG_B64_PATH, "r", encoding="utf-8") as f:
        raw = base64.b64decode(f.read().strip())
    return Image.open(io.BytesIO(raw)).convert("RGBA")


def _glow(base, box, blur=18, alpha=110):
    x0, y0, x1, y1 = map(int, box)
    pad = blur * 3
    layer = Image.new("RGBA", (x1 - x0 + pad * 2, y1 - y0 + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle((pad, pad, pad + x1 - x0, pad + y1 - y0), radius=30,
                        fill=(225, 24, 30, alpha))
    layer = layer.filter(ImageFilter.GaussianBlur(blur))
    base.alpha_composite(layer, (x0 - pad, y0 - pad))


def _day_card(base, x0, y0, x1, y1):
    _glow(base, (x0, y0, x1, y1), blur=18, alpha=105)
    d = ImageDraw.Draw(base)
    d.rounded_rectangle((x0, y0, x1, y1), radius=34, fill=(255, 255, 255, 252),
                        outline=(190, 20, 27, 235), width=6)
    d.rounded_rectangle((x0 + 8, y0 + 8, x1 - 8, y1 - 8), radius=27,
                        outline=(255, 255, 255, 235), width=3)


def _date_icon(base, cx, cy, size):
    d = ImageDraw.Draw(base)
    s = int(size)
    x0, y0 = int(cx - s * .52), int(cy - s * .43)
    x1, y1 = int(cx + s * .52), int(cy + s * .43)
    w = max(4, s // 12)
    d.rounded_rectangle((x0, y0, x1, y1), radius=max(4, s // 9), outline=WHITE, width=w)
    d.line((x0, y0 + s * .20, x1, y0 + s * .20), fill=WHITE, width=w)
    for bx in (x0 + s * .22, x1 - s * .22):
        d.line((bx, y0 - s * .06, bx, y0 + s * .12), fill=WHITE, width=w + 1)


def _date_ribbon(base, text, cy, width=560, height=92):
    cx = W / 2
    x0, y0 = int(cx - width / 2), int(cy - height / 2)
    x1, y1 = int(cx + width / 2), int(cy + height / 2)
    d = ImageDraw.Draw(base)
    _glow(base, (x0, y0, x1, y1), blur=12, alpha=100)
    # Small pointed shoulders give the same tab-over-card construction as the reference.
    pts = [(x0 + 34, y0), (x0 + 70, y0), (x0 + 92, y0 - 22),
           (x1 - 92, y0 - 22), (x1 - 70, y0), (x1 - 34, y0),
           (x1, y0 + 16), (x1, y1 - 16), (x1 - 34, y1),
           (x0 + 34, y1), (x0, y1 - 16), (x0, y0 + 16)]
    d.polygon(pts, fill=RED)
    d.line(pts + [pts[0]], fill=(255, 255, 255, 115), width=3)
    _date_icon(base, x0 + 70, cy, height * .43)
    size = _p._fit_font(d, text, width - 150, int(height * .54), "Bold", min_size=24, rtl=True)
    _p._draw_text(d, (cx + 20, cy), text, size, "Bold", fill=WHITE, anchor="mm", rtl=True)


def _time_plate(base, cx, cy, text, row_h):
    d = ImageDraw.Draw(base)
    h = int(min(125, max(92, row_h * .58)))
    width = max(340, int(h * 1.70))
    slant = int(h * .22)
    x0, x1 = int(cx - width / 2), int(cx + width / 2)
    y0, y1 = int(cy - h / 2), int(cy + h / 2)
    glow = Image.new("RGBA", (width + 80, h + 80), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.rounded_rectangle((40, 40, width + 39, h + 39), radius=int(h * .20), fill=(181, 10, 16, 130))
    glow = glow.filter(ImageFilter.GaussianBlur(14))
    base.alpha_composite(glow, (x0 - 40, y0 - 40))
    poly = [(x0 + slant, y0), (x1 - slant, y0), (x1, cy),
            (x1 - slant, y1), (x0 + slant, y1), (x0, cy)]
    d.polygon(poly, fill=RED)
    d.line(poly + [poly[0]], fill=(255, 255, 255, 120), width=3)
    d.line((x0 + slant + 18, y0 + 9, x1 - slant - 18, y0 + 9),
           fill=(255, 255, 255, 95), width=3)
    size = _p._fit_font(d, text, width - 65, int(h * .60), "ExtraBold", min_size=32,
                        rtl=False, role="time")
    _p._draw_text(d, (cx, cy - 2), text, size, "ExtraBold", fill=WHITE,
                  anchor="mm", rtl=False, role="time")


def _match_row(base, match, y0, y1):
    mid = (y0 + y1) / 2
    rh = y1 - y0
    center = W / 2
    home = match.get("home") or {}
    away = match.get("away") or {}

    # Reference composition: home on the right, away on the left.
    home_logo_x, away_logo_x = 1710, 290
    logo_size = int(max(110, min(190, rh * .72)))
    _p._paste_contained(base, _p._logo_path(home.get("logo"), home.get("logo_dir", "logos")),
                        home_logo_x, mid, logo_size, logo_size)
    _p._paste_contained(base, _p._logo_path(away.get("logo"), away.get("logo_dir", "logos")),
                        away_logo_x, mid, logo_size, logo_size)

    d = ImageDraw.Draw(base)
    name_size = int(max(30, min(48, rh * .24)))
    home_name = (home.get("name_ar") or "").strip()
    away_name = (away.get("name_ar") or "").strip()
    if home_name:
        s = _p._fit_font(d, home_name, 450, name_size, "Bold", min_size=24, rtl=True)
        _p._draw_text(d, (home_logo_x - logo_size * .62, mid), home_name, s, "Bold",
                      fill=TEXT, anchor="rm", rtl=True)
    if away_name:
        s = _p._fit_font(d, away_name, 450, name_size, "Bold", min_size=24, rtl=True)
        _p._draw_text(d, (away_logo_x + logo_size * .62, mid), away_name, s, "Bold",
                      fill=TEXT, anchor="lm", rtl=True)

    _time_plate(base, center, mid, (match.get("time") or "16:30").strip(), rh)


def _draw_day(base, day, y, card_h, date_h, row_h):
    x0, x1 = 155, W - 155
    card_y0, card_y1 = int(y + date_h * .25), int(y + card_h)
    _day_card(base, x0, card_y0, x1, card_y1)
    _date_ribbon(base, (day.get("date_label") or "").strip(), y + date_h / 2,
                 width=560, height=date_h)

    matches = day.get("matches") or []
    content_top = card_y0 + 28
    content_bottom = card_y1 - 24
    usable = content_bottom - content_top
    actual_row_h = usable / max(1, len(matches))
    for i, match in enumerate(matches):
        ry0 = content_top + i * actual_row_h
        ry1 = content_top + (i + 1) * actual_row_h
        if i:
            d = ImageDraw.Draw(base)
            d.line((x0 + 55, ry0, x1 - 55, ry0), fill=(176, 12, 18, 42), width=2)
        _match_row(base, match, ry0, ry1)


def render_kickoff(matchweek, days: list[dict], brand_logo: str | None = None,
                   background: str | None = None, scale: float = 1.0) -> Image.Image:
    # Supplied reference background is the default.
    try:
        base = _load_reference_background()
    except Exception:
        bg_path = _p.KICKOFF_BG_PATH if os.path.exists(_p.KICKOFF_BG_PATH) else _p.BG_PATH
        base = Image.open(bg_path).convert("RGBA")

    if background:
        candidate = os.path.join(_p.STATIC, "img", os.path.basename(background))
        if os.path.exists(candidate):
            base = Image.open(candidate).convert("RGBA")
    if base.size != (W, H):
        base = base.resize((W, H), Image.LANCZOS)

    days = [d for d in days if d.get("matches")]
    d = ImageDraw.Draw(base)

    # Header deliberately enlarged to match the reference hierarchy.
    _p._paste_brand_logo(base, W / 2, 155, 225, 225, spec=brand_logo)
    _p._draw_text(d, (W / 2, 330), "KICK OFF", 154, "ExtraBold", fill=WHITE,
                  anchor="mm", rtl=False, role="time")
    label = f"MATCHWEEK #{int(matchweek):02d}" if str(matchweek).isdigit() else f"MATCHWEEK {matchweek}"
    _p._draw_text(d, (W / 2, 440), label, 64, "Bold", fill=WHITE,
                  anchor="mm", rtl=False, role="time")
    half = _p._text_w(d, label, _p._font(64, "Bold", "time"), rtl=False) / 2
    _p._flank_lines(base, W / 2, 440, half, (255, 255, 255, 155), ext=125, gap=28, width=3)

    if not days:
        return base.resize((int(W * scale), int(H * scale)), Image.LANCZOS).convert("RGB") if scale != 1 else base.convert("RGB")

    # Four date groups fit into the same vertical rhythm as the supplied poster.
    top = 535
    bottom = 2390
    date_h = 88
    day_gap = 34
    row_h = 205
    rows = sum(len(day.get("matches") or []) for day in days)
    total = sum(date_h + 25 + len(day.get("matches") or []) * row_h + 25 for day in days) + max(0, len(days)-1) * day_gap
    if total > bottom - top:
        factor = (bottom - top) / total
        row_h = max(135, int(row_h * factor))
        day_gap = max(18, int(day_gap * factor))

    # Recompute and center the complete fixture stack.
    total = sum(date_h + 25 + len(day.get("matches") or []) * row_h + 25 for day in days) + max(0, len(days)-1) * day_gap
    y = top + max(0, (bottom - top - total) / 2)
    for day in days:
        count = len(day.get("matches") or [])
        card_h = date_h + 25 + count * row_h + 25
        _draw_day(base, day, y, card_h, date_h, row_h)
        y += card_h + day_gap

    if scale != 1.0:
        base = base.resize((int(W * scale), int(H * scale)), Image.LANCZOS)
    return base.convert("RGB")
