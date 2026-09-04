"""4:5 reference-model KICK OFF renderer."""
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
BG_B64 = os.path.join(p.STATIC, "img", "bg-kickoff-reference.b64")


def _load_image(path):
    im = Image.open(path).convert("RGBA")
    return im.resize((W, H), Image.LANCZOS) if im.size != (W, H) else im


def _load_reference_b64():
    with open(BG_B64, "r", encoding="utf-8") as f:
        raw = base64.b64decode(f.read().strip(), validate=True)
    with Image.open(io.BytesIO(raw)) as src:
        src.load()
        return src.convert("RGBA").resize((W, H), Image.LANCZOS)


def _bg(background=None):
    """Use the supplied reference background by default.

    The legacy bg-kickoff.png is kept only as a fallback so the model does not
    silently switch back to the older background during preview generation.
    """
    if background:
        candidate = os.path.join(p.STATIC, "img", os.path.basename(background))
        if os.path.exists(candidate) and os.path.basename(candidate) != "bg-kickoff.png":
            try:
                return _load_image(candidate)
            except Exception:
                pass
    try:
        return _load_reference_b64()
    except Exception:
        pass
    for path in (p.KICKOFF_BG_PATH, p.BG_PATH):
        if os.path.exists(path):
            try:
                return _load_image(path)
            except Exception:
                pass
    return Image.new("RGBA", (W, H), (88, 0, 8, 255))


def _glass_card(im, box):
    x0, y0, x1, y1 = map(int, box)
    d = ImageDraw.Draw(im)
    glow = Image.new("RGBA", im.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.rounded_rectangle((x0, y0, x1, y1), radius=44, fill=(255, 255, 255, 48), outline=(255, 255, 255, 120), width=8)
    glow = glow.filter(ImageFilter.GaussianBlur(20))
    im.alpha_composite(glow)
    d.rounded_rectangle((x0, y0, x1, y1), radius=44, fill=(250, 250, 250, 236), outline=(255, 255, 255, 232), width=7)
    d.rounded_rectangle((x0 + 10, y0 + 10, x1 - 10, y1 - 10), radius=36, fill=(255, 255, 255, 34), outline=(196, 24, 30, 125), width=3)


def _date_tab(im, text, cy, width=720, height=94):
    d = ImageDraw.Draw(im)
    cx = W // 2
    x0, x1 = int(cx - width / 2), int(cx + width / 2)
    y0, y1 = int(cy - height / 2), int(cy + height / 2)
    pts = [(x0 + 34, y0), (x0 + 82, y0), (x0 + 108, y0 - 20), (x1 - 108, y0 - 20), (x1 - 82, y0), (x1 - 34, y0), (x1, y0 + 18), (x1, y1 - 18), (x1 - 34, y1), (x0 + 34, y1), (x0, y1 - 18), (x0, y0 + 18)]
    d.polygon(pts, fill=RED)
    d.line(pts + [pts[0]], fill=(255, 255, 255, 180), width=3)
    gx, gy, s = x0 + 60, int(cy), 28
    d.rounded_rectangle((gx - s, gy - s + 2, gx + s, gy + s), radius=6, outline=WHITE, width=5)
    d.line((gx - s, gy - 5, gx + s, gy - 5), fill=WHITE, width=4)
    d.line((gx - 13, gy - s - 3, gx - 13, gy - 12), fill=WHITE, width=5)
    d.line((gx + 13, gy - s - 3, gx + 13, gy - 12), fill=WHITE, width=5)
    fs = p._fit_font(d, text, width - 145, 52, "Bold", min_size=28, rtl=True)
    p._draw_text(d, (cx + 30, cy), text, fs, "Bold", fill=WHITE, anchor="mm", rtl=True)


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
    logo = int(max(145, min(205, rh * .98)))
    home, away = match.get("home") or {}, match.get("away") or {}
    for side, x in ((home, 1690), (away, 310)):
        try:
            path = p._logo_path(side.get("logo"), side.get("logo_dir", "logos"))
            p._paste_contained(im, path, x, cy, logo, logo)
        except Exception:
            pass
    name_fs = int(max(38, min(56, rh * .29)))
    hn, an = (home.get("name_ar") or "").strip(), (away.get("name_ar") or "").strip()
    if hn:
        fs = p._fit_font(d, hn, 500, name_fs, "Bold", min_size=30, rtl=True)
        p._draw_text(d, (1515, cy), hn, fs, "Bold", fill=TEXT, anchor="rm", rtl=True)
    if an:
        fs = p._fit_font(d, an, 500, name_fs, "Bold", min_size=30, rtl=True)
        p._draw_text(d, (485, cy), an, fs, "Bold", fill=TEXT, anchor="lm", rtl=True)
    chev = max(22, int(rh * .12))
    p._draw_text(d, (850, cy), "«", chev, "Bold", fill=RED, anchor="mm", rtl=False)
    p._draw_text(d, (1150, cy), "»", chev, "Bold", fill=RED, anchor="mm", rtl=False)
    _time(im, (match.get("time") or "16:30").strip(), cy, int(min(120, max(104, rh * .64))))


def _day(im, day, y, card_h, row_h):
    x0, x1 = 120, 1880
    card_y0, card_y1 = int(y + 38), int(y + card_h)
    _glass_card(im, (x0, card_y0, x1, card_y1))
    _date_tab(im, (day.get("date_label") or "").strip(), y + 38)
    matches = day.get("matches") or []
    top, bottom = card_y0 + 32, card_y1 - 26
    actual = (bottom - top) / max(1, len(matches))
    for i, m in enumerate(matches):
        a, b = top + i * actual, top + (i + 1) * actual
        if i:
            ImageDraw.Draw(im).line((x0 + 50, a, x1 - 50, a), fill=(175, 25, 30, 72), width=2)
        _row(im, m, a, b)


def render_kickoff(matchweek, days: list[dict], brand_logo=None, background=None, scale=1.0):
    im = _bg(background)
    d = ImageDraw.Draw(im)
    try:
        p._paste_brand_logo(im, W / 2, 178, 300, 300, spec=brand_logo)
    except Exception:
        pass
    p._draw_text(d, (W / 2, 390), "KICK OFF", 215, "ExtraBold", fill=WHITE, anchor="mm", rtl=False, role="time")
    label = f"MATCHWEEK #{int(matchweek):02d}" if str(matchweek).isdigit() else f"MATCHWEEK {matchweek}"
    p._draw_text(d, (W / 2, 515), label, 88, "Bold", fill=WHITE, anchor="mm", rtl=False, role="time")
    half = p._text_w(d, label, p._font(88, "Bold", "time"), rtl=False) / 2
    p._flank_lines(im, W / 2, 515, half, (255, 255, 255, 175), ext=135, gap=30, width=3)
    days = [x for x in days if x.get("matches")]
    if not days:
        return im.convert("RGB")
    top, bottom = 600, 2410
    date_h, gap = 94, 26
    row_h = 166
    total = sum(date_h + 38 + len(x.get("matches") or []) * row_h + 26 for x in days) + max(0, len(days) - 1) * gap
    if total > bottom - top:
        row_h = max(145, int(row_h * ((bottom - top) / total)))
    total = sum(date_h + 38 + len(x.get("matches") or []) * row_h + 26 for x in days) + max(0, len(days) - 1) * gap
    y = top + max(0, (bottom - top - total) / 2)
    for day in days:
        card_h = date_h + 38 + len(day.get("matches") or []) * row_h + 26
        _day(im, day, y, card_h, row_h)
        y += card_h + gap
    if scale != 1.0:
        im = im.resize((int(W * scale), int(H * scale)), Image.LANCZOS)
    return im.convert("RGB")
