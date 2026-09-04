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
    """Use the supplied reference background by default, with safe fallbacks."""
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
    # Very restrained outer glow: the card should feel luminous, not neon.
    glow = Image.new("RGBA", im.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.rounded_rectangle((x0, y0, x1, y1), radius=42,
                         fill=(255, 255, 255, 26),
                         outline=(255, 255, 255, 92), width=5)
    glow = glow.filter(ImageFilter.GaussianBlur(13))
    im.alpha_composite(glow)
    d.rounded_rectangle((x0, y0, x1, y1), radius=42,
                        fill=(250, 250, 250, 232),
                        outline=(255, 255, 255, 238), width=6)
    d.rounded_rectangle((x0 + 9, y0 + 9, x1 - 9, y1 - 9), radius=34,
                        fill=(255, 255, 255, 22),
                        outline=(196, 24, 30, 105), width=3)


def _date_tab(im, text, cy, width=670, height=84):
    d = ImageDraw.Draw(im)
    cx = W // 2
    x0, x1 = int(cx - width / 2), int(cx + width / 2)
    y0, y1 = int(cy - height / 2), int(cy + height / 2)
    pts = [
        (x0 + 34, y0), (x0 + 82, y0), (x0 + 106, y0 - 18),
        (x1 - 106, y0 - 18), (x1 - 82, y0), (x1 - 34, y0),
        (x1, y0 + 17), (x1, y1 - 17), (x1 - 34, y1),
        (x0 + 34, y1), (x0, y1 - 17), (x0, y0 + 17)
    ]
    d.polygon(pts, fill=RED)
    d.line(pts + [pts[0]], fill=(255, 255, 255, 175), width=3)

    gx, gy, s = x0 + 58, int(cy), 26
    d.rounded_rectangle((gx - s, gy - s + 2, gx + s, gy + s),
                        radius=6, outline=WHITE, width=5)
    d.line((gx - s, gy - 5, gx + s, gy - 5), fill=WHITE, width=4)
    d.line((gx - 13, gy - s - 3, gx - 13, gy - 12), fill=WHITE, width=5)
    d.line((gx + 13, gy - s - 3, gx + 13, gy - 12), fill=WHITE, width=5)

    fs = p._fit_font(d, text, width - 135, 48, "Bold", min_size=28, rtl=True)
    p._draw_text(d, (cx + 28, cy), text, fs, "Bold",
                 fill=WHITE, anchor="mm", rtl=True)


def _time(im, text, cy, h=108):
    """Clean central score plate: no black drop shadow, only a restrained red halo."""
    d = ImageDraw.Draw(im)
    w, sl = 315, 27
    cx = W // 2
    x0, x1 = cx - w // 2, cx + w // 2
    y0, y1 = int(cy - h / 2), int(cy + h / 2)

    # Red/white optical glow only. Never use a black shadow behind the clock.
    glow = Image.new("RGBA", (w + 70, h + 70), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gpoly = [(35 + sl, 35), (35 + w - sl, 35), (35 + w, 35 + h / 2),
             (35 + w - sl, 35 + h), (35 + sl, 35 + h), (35, 35 + h / 2)]
    gd.polygon(gpoly, fill=(150, 8, 15, 82))
    glow = glow.filter(ImageFilter.GaussianBlur(8))
    im.alpha_composite(glow, (x0 - 35, y0 - 35))

    poly = [(x0 + sl, y0), (x1 - sl, y0), (x1, cy),
            (x1 - sl, y1), (x0 + sl, y1), (x0, cy)]
    d.polygon(poly, fill=(192, 12, 20, 255))
    d.line(poly + [poly[0]], fill=(255, 255, 255, 215), width=4)
    d.line((x0 + sl + 15, y0 + 8, x1 - sl - 15, y0 + 8),
           fill=(255, 255, 255, 120), width=3)
    d.line((x0 + 14, cy, x0 + sl + 3, y0 + 13),
           fill=(255, 255, 255, 115), width=2)
    d.line((x1 - 14, cy, x1 - sl - 3, y0 + 13),
           fill=(255, 255, 255, 115), width=2)

    fs = p._fit_font(d, text, w - 34, 76, "ExtraBold",
                     min_size=42, rtl=False, role="time")
    p._draw_text(d, (cx, cy - 1), text, fs, "ExtraBold",
                 fill=WHITE, anchor="mm", rtl=False, role="time")


def _row(im, match, y0, y1):
    d = ImageDraw.Draw(im)
    cy = (y0 + y1) / 2
    rh = y1 - y0
    logo = int(max(132, min(180, rh * .84)))
    home, away = match.get("home") or {}, match.get("away") or {}

    # Large, balanced crests matching the reference poster.
    for side, x in ((home, 1690), (away, 310)):
        try:
            path = p._logo_path(side.get("logo"), side.get("logo_dir", "logos"))
            p._paste_contained(im, path, x, cy, logo, logo)
        except Exception:
            pass

    # Wider type zones, with a deliberate gap before the central clock.
    name_fs = int(max(38, min(54, rh * .28)))
    hn = (home.get("name_ar") or "").strip()
    an = (away.get("name_ar") or "").strip()
    if hn:
        fs = p._fit_font(d, hn, 360, name_fs, "Bold", min_size=29, rtl=True)
        p._draw_text(d, (1550, cy), hn, fs, "Bold",
                     fill=TEXT, anchor="rm", rtl=True)
    if an:
        fs = p._fit_font(d, an, 360, name_fs, "Bold", min_size=29, rtl=True)
        p._draw_text(d, (450, cy), an, fs, "Bold",
                     fill=TEXT, anchor="lm", rtl=True)

    # Small chevrons sit outside the clock instead of being swallowed by it.
    chev = max(18, int(rh * .09))
    p._draw_text(d, (790, cy), "«", chev, "Bold", fill=RED,
                 anchor="mm", rtl=False)
    p._draw_text(d, (1210, cy), "»", chev, "Bold", fill=RED,
                 anchor="mm", rtl=False)
    _time(im, (match.get("time") or "16:30").strip(), cy,
          int(min(112, max(98, rh * .60))))


def _day(im, day, y, card_h, row_h):
    x0, x1 = 120, 1880
    card_y0, card_y1 = int(y + 34), int(y + card_h)
    _glass_card(im, (x0, card_y0, x1, card_y1))
    _date_tab(im, (day.get("date_label") or "").strip(), y + 34)

    matches = day.get("matches") or []
    top, bottom = card_y0 + 32, card_y1 - 22
    actual = (bottom - top) / max(1, len(matches))
    for i, m in enumerate(matches):
        a, b = top + i * actual, top + (i + 1) * actual
        if i:
            ImageDraw.Draw(im).line(
                (x0 + 48, a, x1 - 48, a),
                fill=(175, 25, 30, 55), width=2
            )
        _row(im, m, a, b)


def render_kickoff(matchweek, days: list[dict], brand_logo=None,
                   background=None, scale=1.0):
    """Render on the native 2000x2500 canvas (4:5), independent of browser size."""
    im = _bg(background)
    d = ImageDraw.Draw(im)

    # Header follows a fixed 4:5 grid: logo -> title -> week -> fixtures.
    try:
        p._paste_brand_logo(im, W / 2, 138, 205, 205, spec=brand_logo)
    except Exception:
        pass

    p._draw_text(d, (W / 2, 326), "KICK OFF", 178, "ExtraBold",
                 fill=WHITE, anchor="mm", rtl=False, role="time")

    label = (f"MATCHWEEK #{int(matchweek):02d}"
             if str(matchweek).isdigit()
             else f"MATCHWEEK {matchweek}")
    p._draw_text(d, (W / 2, 455), label, 72, "Bold",
                 fill=WHITE, anchor="mm", rtl=False, role="time")
    half = p._text_w(d, label, p._font(72, "Bold", "time"), rtl=False) / 2
    p._flank_lines(im, W / 2, 455, half,
                   (255, 255, 255, 175), ext=125, gap=28, width=3)

    days = [x for x in days if x.get("matches")]
    if not days:
        return im.convert("RGB")

    # Fixture zone uses the lower 72% of the poster. Rows stay readable rather
    # than collapsing to tiny dashboard-like lines.
    top, bottom = 535, 2390
    date_h, card_offset, inner_bottom, gap = 80, 32, 20, 18
    row_h = 170

    def stack_height(rh):
        return sum(date_h + card_offset + len(x.get("matches") or []) * rh
                   + inner_bottom for x in days) + max(0, len(days) - 1) * gap

    available = bottom - top
    total = stack_height(row_h)
    if total > available:
        row_h = max(150, int(row_h * available / total))

    total = stack_height(row_h)
    y = top + max(0, (available - total) / 2)

    for day in days:
        card_h = date_h + card_offset + len(day.get("matches") or []) * row_h + inner_bottom
        _day(im, day, y, card_h, row_h)
        y += card_h + gap

    if scale != 1.0:
        im = im.resize((int(W * scale), int(H * scale)), Image.LANCZOS)
    return im.convert("RGB")
