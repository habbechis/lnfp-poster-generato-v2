"""4:5 reference-model KICK OFF renderer.

The data/API remain unchanged. This module recreates the supplied visual model
as a deterministic 2000x2500 composition, with translucent glass match cards,
red date tabs, large beveled kickoff plates, and the supplied background.
"""
from __future__ import annotations

import base64
import io
import os
from PIL import Image, ImageDraw, ImageFilter
from . import poster as p

W, H = 2000, 2500
WHITE = (255, 255, 255, 255)
TEXT = (32, 22, 24, 255)
RED = (184, 10, 18, 255)
RED2 = (220, 22, 28, 255)
BG_B64 = os.path.join(p.STATIC, "img", "bg-kickoff-reference.b64")


def _bg():
    with open(BG_B64, "r", encoding="utf-8") as f:
        im = Image.open(io.BytesIO(base64.b64decode(f.read().strip()))).convert("RGBA")
    return im.resize((W, H), Image.LANCZOS) if im.size != (W, H) else im


def _glass_card(im, box):
    x0, y0, x1, y1 = map(int, box)
    d = ImageDraw.Draw(im)
    glow = Image.new("RGBA", im.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.rounded_rectangle((x0, y0, x1, y1), radius=42, fill=(255, 255, 255, 48), outline=(255, 255, 255, 120), width=7)
    glow = glow.filter(ImageFilter.GaussianBlur(18))
    im.alpha_composite(glow)
    # translucent white glass, not opaque white
    d.rounded_rectangle((x0, y0, x1, y1), radius=42, fill=(250, 250, 250, 226), outline=(255, 255, 255, 225), width=6)
    d.rounded_rectangle((x0 + 9, y0 + 9, x1 - 9, y1 - 9), radius=34, fill=(255, 255, 255, 38), outline=(196, 24, 30, 120), width=3)


def _date_tab(im, text, cy, width=650, height=86):
    d = ImageDraw.Draw(im)
    cx = W // 2
    x0, x1 = int(cx - width / 2), int(cx + width / 2)
    y0, y1 = int(cy - height / 2), int(cy + height / 2)
    pts = [(x0 + 32, y0), (x0 + 76, y0), (x0 + 100, y0 - 20), (x1 - 100, y0 - 20), (x1 - 76, y0), (x1 - 32, y0), (x1, y0 + 17), (x1, y1 - 17), (x1 - 32, y1), (x0 + 32, y1), (x0, y1 - 17), (x0, y0 + 17)]
    d.polygon(pts, fill=RED)
    d.line(pts + [pts[0]], fill=(255, 255, 255, 170), width=3)
    # calendar glyph
    gx, gy, s = x0 + 58, int(cy), 27
    d.rounded_rectangle((gx - s, gy - s + 2, gx + s, gy + s), radius=5, outline=WHITE, width=5)
    d.line((gx - s, gy - 5, gx + s, gy - 5), fill=WHITE, width=4)
    d.line((gx - 13, gy - s - 3, gx - 13, gy - 12), fill=WHITE, width=5)
    d.line((gx + 13, gy - s - 3, gx + 13, gy - 12), fill=WHITE, width=5)
    fs = p._fit_font(d, text, width - 135, 48, "Bold", min_size=28, rtl=True)
    p._draw_text(d, (cx + 28, cy), text, fs, "Bold", fill=WHITE, anchor="mm", rtl=True)


def _time(im, text, cy, h=112):
    d = ImageDraw.Draw(im)
    w, sl = 385, 32
    cx = W // 2
    x0, x1 = cx - w // 2, cx + w // 2
    y0, y1 = int(cy - h / 2), int(cy + h / 2)
    shadow = Image.new("RGBA", (w + 90, h + 90), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle((45, 45, w + 44, h + 44), radius=20, fill=(90, 0, 0, 145))
    shadow = shadow.filter(ImageFilter.GaussianBlur(12))
    im.alpha_composite(shadow, (x0 - 45, y0 - 45))
    poly = [(x0 + sl, y0), (x1 - sl, y0), (x1, cy), (x1 - sl, y1), (x0 + sl, y1), (x0, cy)]
    d.polygon(poly, fill=RED)
    d.line(poly + [poly[0]], fill=(255, 255, 255, 190), width=4)
    d.line((x0 + sl + 18, y0 + 9, x1 - sl - 18, y0 + 9), fill=(255, 255, 255, 110), width=3)
    fs = p._fit_font(d, text, w - 50, 78, "ExtraBold", min_size=40, rtl=False, role="time")
    p._draw_text(d, (cx, cy - 2), text, fs, "ExtraBold", fill=WHITE, anchor="mm", rtl=False, role="time")


def _row(im, match, y0, y1):
    d = ImageDraw.Draw(im)
    cy = (y0 + y1) / 2
    rh = y1 - y0
    logo = int(max(125, min(175, rh * .72)))
    home, away = match.get("home") or {}, match.get("away") or {}
    # right = home, left = away, matching RTL composition
    p._paste_contained(im, p._logo_path(home.get("logo"), home.get("logo_dir", "logos")), 1700, cy, logo, logo)
    p._paste_contained(im, p._logo_path(away.get("logo"), away.get("logo_dir", "logos")), 300, cy, logo, logo)
    name_fs = int(max(34, min(50, rh * .25)))
    hn, an = (home.get("name_ar") or "").strip(), (away.get("name_ar") or "").strip()
    if hn:
        fs = p._fit_font(d, hn, 500, name_fs, "Bold", min_size=28, rtl=True)
        p._draw_text(d, (1535, cy), hn, fs, "Bold", fill=TEXT, anchor="rm", rtl=True)
    if an:
        fs = p._fit_font(d, an, 500, name_fs, "Bold", min_size=28, rtl=True)
        p._draw_text(d, (465, cy), an, fs, "Bold", fill=TEXT, anchor="lm", rtl=True)
    # subtle chevrons beside the time plate
    chev = max(20, int(rh * .11))
    p._draw_text(d, (850, cy), "«", chev, "Bold", fill=RED, anchor="mm", rtl=False)
    p._draw_text(d, (1150, cy), "»", chev, "Bold", fill=RED, anchor="mm", rtl=False)
    _time(im, (match.get("time") or "16:30").strip(), cy, int(min(120, max(104, rh * .62))))


def _day(im, day, y, card_h, row_h):
    x0, x1 = 125, 1875
    card_y0, card_y1 = int(y + 36), int(y + card_h)
    _glass_card(im, (x0, card_y0, x1, card_y1))
    _date_tab(im, (day.get("date_label") or "").strip(), y + 36, width=650, height=86)
    matches = day.get("matches") or []
    top, bottom = card_y0 + 30, card_y1 - 24
    actual = (bottom - top) / max(1, len(matches))
    for i, m in enumerate(matches):
        a, b = top + i * actual, top + (i + 1) * actual
        if i:
            d = ImageDraw.Draw(im)
            d.line((x0 + 48, a, x1 - 48, a), fill=(175, 25, 30, 65), width=2)
        _row(im, m, a, b)


def render_kickoff(matchweek, days: list[dict], brand_logo=None, background=None, scale=1.0):
    im = _bg()
    d = ImageDraw.Draw(im)
    # Fixed 4:5 header geometry from the supplied model.
    p._paste_brand_logo(im, W / 2, 170, 215, 215, spec=brand_logo)
    p._draw_text(d, (W / 2, 365), "KICK OFF", 158, "ExtraBold", fill=WHITE, anchor="mm", rtl=False, role="time")
    label = f"MATCHWEEK #{int(matchweek):02d}" if str(matchweek).isdigit() else f"MATCHWEEK {matchweek}"
    p._draw_text(d, (W / 2, 480), label, 66, "Bold", fill=WHITE, anchor="mm", rtl=False, role="time")
    half = p._text_w(d, label, p._font(66, "Bold", "time"), rtl=False) / 2
    p._flank_lines(im, W / 2, 480, half, (255, 255, 255, 175), ext=125, gap=28, width=3)
    days = [x for x in days if x.get("matches")]
    if not days:
        return im.convert("RGB")
    top, bottom = 560, 2380
    date_h, gap = 86, 32
    row_h = 208
    total = sum(date_h + 36 + len(x.get("matches") or []) * row_h + 24 for x in days) + max(0, len(days) - 1) * gap
    if total > bottom - top:
        row_h = max(150, int(row_h * ((bottom - top) / total)))
    total = sum(date_h + 36 + len(x.get("matches") or []) * row_h + 24 for x in days) + max(0, len(days) - 1) * gap
    y = top + max(0, (bottom - top - total) / 2)
    for day in days:
        card_h = date_h + 36 + len(day.get("matches") or []) * row_h + 24
        _day(im, day, y, card_h, row_h)
        y += card_h + gap
    if scale != 1.0:
        im = im.resize((int(W * scale), int(H * scale)), Image.LANCZOS)
    return im.convert("RGB")
