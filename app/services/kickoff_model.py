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
    glow = Image.new("RGBA", im.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.rounded_rectangle((x0, y0, x1, y1), radius=44,
                         fill=(255, 255, 255, 42),
                         outline=(255, 255, 255, 105), width=7)
    glow = glow.filter(ImageFilter.GaussianBlur(18))
    im.alpha_composite(glow)
    # Slightly translucent so the supplied red background remains visible.
    d.rounded_rectangle((x0, y0, x1, y1), radius=44,
                        fill=(250, 250, 250, 232),
                        outline=(255, 255, 255, 235), width=7)
    d.rounded_rectangle((x0 + 10, y0 + 10, x1 - 10, y1 - 10), radius=36,
                        fill=(255, 255, 255, 30),
                        outline=(196, 24, 30, 118), width=3)


def _date_tab(im, text, cy, width=690, height=88):
    d = ImageDraw.Draw(im)
    cx = W // 2
    x0, x1 = int(cx - width / 2), int(cx + width / 2)
    y0, y1 = int(cy - height / 2), int(cy + height / 2)
    pts = [
        (x0 + 34, y0), (x0 + 82, y0), (x0 + 108, y0 - 20),
        (x1 - 108, y0 - 20), (x1 - 82, y0), (x1 - 34, y0),
        (x1, y0 + 18), (x1, y1 - 18), (x1 - 34, y1),
        (x0 + 34, y1), (x0, y1 - 18), (x0, y0 + 18)
    ]
    d.polygon(pts, fill=RED)
    d.line(pts + [pts[0]], fill=(255, 255, 255, 180), width=3)

    gx, gy, s = x0 + 58, int(cy), 27
    d.rounded_rectangle((gx - s, gy - s + 2, gx + s, gy + s),
                        radius=6, outline=WHITE, width=5)
    d.line((gx - s, gy - 5, gx + s, gy - 5), fill=WHITE, width=4)
    d.line((gx - 13, gy - s - 3, gx - 13, gy - 12), fill=WHITE, width=5)
    d.line((gx + 13, gy - s - 3, gx + 13, gy - 12), fill=WHITE, width=5)

    fs = p._fit_font(d, text, width - 135, 50, "Bold", min_size=28, rtl=True)
    p._draw_text(d, (cx + 28, cy), text, fs, "Bold",
                 fill=WHITE, anchor="mm", rtl=True)


def _time(im, text, cy, h=116):
    d = ImageDraw.Draw(im)
    w, sl = 375, 31
    cx = W // 2
    x0, x1 = cx - w // 2, cx + w // 2
    y0, y1 = int(cy - h / 2), int(cy + h / 2)

    shadow = Image.new("RGBA", (w + 90, h + 90), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle((45, 45, w + 44, h + 44), radius=20,
                         fill=(75, 0, 0, 135))
    shadow = shadow.filter(ImageFilter.GaussianBlur(11))
    im.alpha_composite(shadow, (x0 - 45, y0 - 45))

    poly = [(x0 + sl, y0), (x1 - sl, y0), (x1, cy),
            (x1 - sl, y1), (x0 + sl, y1), (x0, cy)]
    d.polygon(poly, fill=RED)
    d.line(poly + [poly[0]], fill=(255, 255, 255, 190), width=4)
    d.line((x0 + sl + 18, y0 + 9, x1 - sl - 18, y0 + 9),
           fill=(255, 255, 255, 105), width=3)

    fs = p._fit_font(d, text, w - 44, 78, "ExtraBold",
                     min_size=40, rtl=False, role="time")
    p._draw_text(d, (cx, cy - 2), text, fs, "ExtraBold",
                 fill=WHITE, anchor="mm", rtl=False, role="time")


def _row(im, match, y0, y1):
    d = ImageDraw.Draw(im)
    cy = (y0 + y1) / 2
    rh = y1 - y0

    # Keep the crest/name zones completely outside the central time plate.
    logo = int(max(132, min(190, rh * .90)))
    home, away = match.get("home") or {}, match.get("away") or {}

    for side, x in ((home, 1690), (away, 310)):
        try:
            path = p._logo_path(side.get("logo"), side.get("logo_dir", "logos"))
            p._paste_contained(im, path, x, cy, logo, logo)
        except Exception:
            pass

    name_fs = int(max(35, min(52, rh * .27)))
    hn = (home.get("name_ar") or "").strip()
    an = (away.get("name_ar") or "").strip()

    # Narrower text columns prevent Arabic names from colliding with the clock.
    if hn:
        fs = p._fit_font(d, hn, 350, name_fs, "Bold", min_size=27, rtl=True)
        p._draw_text(d, (1635, cy), hn, fs, "Bold",
                     fill=TEXT, anchor="rm", rtl=True)
    if an:
        fs = p._fit_font(d, an, 350, name_fs, "Bold", min_size=27, rtl=True)
        p._draw_text(d, (365, cy), an, fs, "Bold",
                     fill=TEXT, anchor="lm", rtl=True)

    chev = max(20, int(rh * .105))
    p._draw_text(d, (790, cy), "«", chev, "Bold", fill=RED,
                 anchor="mm", rtl=False)
    p._draw_text(d, (1210, cy), "»", chev, "Bold", fill=RED,
                 anchor="mm", rtl=False)
    _time(im, (match.get("time") or "16:30").strip(), cy,
          int(min(118, max(102, rh * .64))))


def _day(im, day, y, card_h, row_h):
    x0, x1 = 120, 1880
    card_y0, card_y1 = int(y + 38), int(y + card_h)
    _glass_card(im, (x0, card_y0, x1, card_y1))
    _date_tab(im, (day.get("date_label") or "").strip(), y + 38)

    matches = day.get("matches") or []
    top, bottom = card_y0 + 30, card_y1 - 24
    actual = (bottom - top) / max(1, len(matches))
    for i, m in enumerate(matches):
        a, b = top + i * actual, top + (i + 1) * actual
        if i:
            ImageDraw.Draw(im).line(
                (x0 + 48, a, x1 - 48, a),
                fill=(175, 25, 30, 65), width=2
            )
        _row(im, m, a, b)


def render_kickoff(matchweek, days: list[dict], brand_logo=None,
                   background=None, scale=1.0):
    """Render a poster on a fixed 2000x2500 canvas (4:5).

    Composition is deliberately fixed to the poster's native coordinate
    system: a breathing header, a centered fixture stack, and no browser/UI
    dimensions are used to determine the layout.
    """
    im = _bg(background)
    d = ImageDraw.Draw(im)

    # --- Header zone: logo -> title -> week label, with real breathing room.
    try:
        p._paste_brand_logo(im, W / 2, 165, 215, 215, spec=brand_logo)
    except Exception:
        pass

    p._draw_text(d, (W / 2, 380), "KICK OFF", 178, "ExtraBold",
                 fill=WHITE, anchor="mm", rtl=False, role="time")

    label = (f"MATCHWEEK #{int(matchweek):02d}"
             if str(matchweek).isdigit()
             else f"MATCHWEEK {matchweek}")
    p._draw_text(d, (W / 2, 505), label, 76, "Bold",
                 fill=WHITE, anchor="mm", rtl=False, role="time")
    half = p._text_w(d, label, p._font(76, "Bold", "time"), rtl=False) / 2
    p._flank_lines(im, W / 2, 505, half,
                   (255, 255, 255, 175), ext=130, gap=28, width=3)

    days = [x for x in days if x.get("matches")]
    if not days:
        return im.convert("RGB")

    # --- Fixture zone: occupies roughly the lower 70% of the 4:5 poster.
    # Compact overhead + adaptive rows keep every day/card visually legible.
    top, bottom = 610, 2390
    date_h, card_offset, inner_bottom, gap = 82, 34, 22, 22
    row_h = 158

    def stack_height(rh):
        return sum(date_h + card_offset + len(x.get("matches") or []) * rh
                   + inner_bottom for x in days) + max(0, len(days) - 1) * gap

    available = bottom - top
    total = stack_height(row_h)
    if total > available:
        row_h = max(145, int(row_h * available / total))

    total = stack_height(row_h)
    y = top + max(0, (available - total) / 2)

    for day in days:
        card_h = date_h + card_offset + len(day.get("matches") or []) * row_h + inner_bottom
        _day(im, day, y, card_h, row_h)
        y += card_h + gap

    if scale != 1.0:
        im = im.resize((int(W * scale), int(H * scale)), Image.LANCZOS)
    return im.convert("RGB")
