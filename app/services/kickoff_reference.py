"""Reference-driven KICK OFF poster renderer.

This module deliberately keeps the existing API/data model untouched. It only
replaces the visual renderer used by the KICK OFF endpoints.
"""
from __future__ import annotations

import base64
import io
import math
import os
from typing import Iterable

from PIL import Image, ImageDraw, ImageFilter

from . import poster as _p

W, H = _p.W, _p.H
WHITE = (255, 255, 255, 255)
TEXT = (24, 28, 48, 255)
RED = (176, 12, 18, 255)
RED_DARK = (119, 6, 11, 255)
RED_SOFT = (214, 32, 38, 90)
BORDER = (177, 13, 20, 210)
REFERENCE_BG_B64_PATH = os.path.join(_p.STATIC, "img", "bg-kickoff-reference.b64")


def _load_reference_background():
    """Load the supplied reference background stored as a deploy-safe base64 asset."""
    with open(REFERENCE_BG_B64_PATH, "r", encoding="utf-8") as f:
        raw = base64.b64decode(f.read().strip())
    return Image.open(io.BytesIO(raw)).convert("RGBA")


def _rounded_shadow(base, box, radius, blur=24):
    x0, y0, x1, y1 = map(int, box)
    pad = blur * 3
    layer = Image.new("RGBA", (x1 - x0 + pad * 2, y1 - y0 + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle((pad, pad, pad + x1 - x0, pad + y1 - y0), radius=radius, fill=RED_SOFT)
    layer = layer.filter(ImageFilter.GaussianBlur(blur))
    base.alpha_composite(layer, (x0 - pad, y0 - pad))


def _card(base, box, radius=28):
    x0, y0, x1, y1 = map(int, box)
    _rounded_shadow(base, box, radius, blur=22)
    d = ImageDraw.Draw(base)
    d.rounded_rectangle((x0, y0, x1, y1), radius=radius, fill=(255, 255, 255, 250), outline=BORDER, width=5)
    d.rounded_rectangle((x0 + 7, y0 + 7, x1 - 7, y1 - 7), radius=max(8, radius - 7), outline=(255, 255, 255, 230), width=2)


def _date_icon(base, cx, cy, size):
    d = ImageDraw.Draw(base)
    s = int(size)
    x0, y0 = int(cx - s * .52), int(cy - s * .44)
    x1, y1 = int(cx + s * .52), int(cy + s * .44)
    r = max(5, s // 10)
    d.rounded_rectangle((x0, y0, x1, y1), radius=r, outline=WHITE, width=max(4, s // 13))
    d.line((x0, y0 + s * .22, x1, y0 + s * .22), fill=WHITE, width=max(4, s // 13))
    for bx in (x0 + s * .23, x1 - s * .23):
        d.line((bx, y0 - s * .06, bx, y0 + s * .13), fill=WHITE, width=max(5, s // 10))
    d.ellipse((cx - s * .06, cy + s * .05, cx + s * .06, cy + s * .17), fill=WHITE)


def _date_badge(base, text, cy, width=560, height=104):
    cx = W / 2
    x0, y0 = cx - width / 2, cy - height / 2
    x1, y1 = cx + width / 2, cy + height / 2
    _rounded_shadow(base, (x0, y0, x1, y1), int(height * .28), blur=14)
    d = ImageDraw.Draw(base)
    d.rounded_rectangle((x0, y0, x1, y1), radius=int(height * .28), fill=RED)
    d.line((x0 + 28, y0 + 4, x1 - 28, y0 + 4), fill=(255, 255, 255, 105), width=3)
    d.rounded_rectangle((x0, y0, x1, y1), radius=int(height * .28), outline=(255, 255, 255, 80), width=3)
    _date_icon(base, x0 + 68, cy, height * .47)
    draw = ImageDraw.Draw(base)
    size = _p._fit_font(draw, text, width - 145, int(height * .48), "Bold", min_size=24, rtl=True)
    _p._draw_text(draw, (cx + 24, cy), text, size, "Bold", fill=WHITE, anchor="mm")


def _time_plate(base, cx, cy, text, height):
    d = ImageDraw.Draw(base)
    h = int(height)
    tw = _p._text_w(d, text, _p._font(max(24, int(h * .47)), "ExtraBold", "time"), rtl=False)
    width = max(330, int(tw + h * 1.45))
    slant = int(h * .22)
    x0, x1 = int(cx - width / 2), int(cx + width / 2)
    y0, y1 = int(cy - h / 2), int(cy + h / 2)
    glow = Image.new("RGBA", (width + 80, h + 80), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.rounded_rectangle((40, 40, width + 39, h + 39), radius=int(h * .18), fill=(176, 12, 18, 110))
    glow = glow.filter(ImageFilter.GaussianBlur(16))
    base.alpha_composite(glow, (x0 - 40, y0 - 40))
    poly = [(x0 + slant, y0), (x1 - slant, y0), (x1, y0 + h / 2), (x1 - slant, y1), (x0 + slant, y1), (x0, y0 + h / 2)]
    d.polygon(poly, fill=RED)
    d.line(poly + [poly[0]], fill=(255, 255, 255, 105), width=3)
    d.line((x0 + slant + 18, y0 + 10, x1 - slant - 18, y0 + 10), fill=(255, 255, 255, 80), width=3)
    size = _p._fit_font(d, text, width - 80, int(h * .52), "ExtraBold", min_size=28, rtl=False, role="time")
    _p._draw_text(d, (cx, cy - 2), text, size, "ExtraBold", fill=WHITE, anchor="mm", rtl=False, role="time")


def _separator(base, y, x0=250, x1=1750):
    d = ImageDraw.Draw(base)
    d.line((x0, y, x1, y), fill=(176, 12, 18, 42), width=2)


def _match_row(base, match, y0, y1):
    card_x0, card_x1 = 155, W - 155
    _card(base, (card_x0, y0, card_x1, y1), radius=30)
    mid = (y0 + y1) / 2
    h = y1 - y0
    center = W / 2
    home = match.get("home") or {}
    away = match.get("away") or {}
    logo_box = max(105, min(185, int(h * .68)))
    home_logo_x = 1515
    away_logo_x = 485
    _p._paste_contained(base, _p._logo_path(home.get("logo"), home.get("logo_dir", "logos")), home_logo_x, mid - 2, logo_box, logo_box)
    _p._paste_contained(base, _p._logo_path(away.get("logo"), away.get("logo_dir", "logos")), away_logo_x, mid - 2, logo_box, logo_box)
    draw = ImageDraw.Draw(base)
    name_size = max(28, min(46, int(h * .19)))
    home_name = (home.get("name_ar") or "").strip()
    away_name = (away.get("name_ar") or "").strip()
    if home_name:
        name_size_h = _p._fit_font(draw, home_name, 420, name_size, "Bold", min_size=24)
        _p._draw_text(draw, (home_logo_x - logo_box * .72, mid), home_name, name_size_h, "Bold", fill=TEXT, anchor="rm")
    if away_name:
        name_size_a = _p._fit_font(draw, away_name, 420, name_size, "Bold", min_size=24)
        _p._draw_text(draw, (away_logo_x + logo_box * .72, mid), away_name, name_size_a, "Bold", fill=TEXT, anchor="lm")
    _time_plate(base, center, mid, (match.get("time") or "16:30").strip(), int(min(112, h * .48)))
    d = ImageDraw.Draw(base)
    d.line((760, mid, 820, mid), fill=(176, 12, 18, 90), width=3)
    d.line((1180, mid, 1240, mid), fill=(176, 12, 18, 90), width=3)


def render_kickoff(matchweek, days: list[dict], brand_logo: str | None = None, background: str | None = None, scale: float = 1.0) -> Image.Image:
    # The supplied reference image is the default KICK OFF background.
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
    draw = ImageDraw.Draw(base)
    logo_cy = 150
    _p._paste_brand_logo(base, W / 2, logo_cy, 190, 190, spec=brand_logo)
    draw = ImageDraw.Draw(base)
    _p._draw_text(draw, (W / 2, 320), "KICK OFF", 142, "ExtraBold", fill=WHITE, anchor="mm", rtl=False, role="time")
    label = (f"MATCHWEEK #{int(matchweek):02d}" if str(matchweek).isdigit() else f"MATCHWEEK {matchweek}")
    _p._draw_text(draw, (W / 2, 435), label, 60, "Bold", fill=_p.CRYSTAL, anchor="mm", rtl=False, role="time")
    half = _p._text_w(draw, label, _p._font(60, "Bold", "time"), rtl=False) / 2
    _p._flank_lines(base, W / 2, 435, half, (255, 255, 255, 125), ext=115, gap=30, width=3)

    if not days:
        if scale != 1.0:
            base = base.resize((int(W * scale), int(H * scale)), Image.LANCZOS)
        return base.convert("RGB")

    top = 560
    bottom = 2390
    day_gap = 34
    date_h = 104
    row_h = 245
    row_gap = 18
    total = sum(date_h + len(d["matches"]) * row_h + max(0, len(d["matches"]) - 1) * row_gap for d in days) + max(0, len(days) - 1) * day_gap
    if total > bottom - top:
        factor = (bottom - top) / total
        row_h = max(165, int(row_h * factor))
        date_h = max(78, int(date_h * factor))
        row_gap = max(10, int(row_gap * factor))
        day_gap = max(18, int(day_gap * factor))
        total = sum(date_h + len(d["matches"]) * row_h + max(0, len(d["matches"]) - 1) * row_gap for d in days) + max(0, len(days) - 1) * day_gap
    y = top + max(0, (bottom - top - total) / 2)

    for day in days:
        date = (day.get("date_label") or "").strip() or ""
        _date_badge(base, date, y + date_h / 2, width=560, height=date_h)
        y += date_h + 18
        matches = day.get("matches") or []
        for mi, match in enumerate(matches):
            _match_row(base, match, y, y + row_h)
            y += row_h
            if mi < len(matches) - 1:
                _separator(base, y + row_gap / 2)
                y += row_gap
        y += day_gap

    if scale != 1.0:
        base = base.resize((int(W * scale), int(H * scale)), Image.LANCZOS)
    return base.convert("RGB")
