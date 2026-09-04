"""Premium 4:5 KICK OFF poster renderer with clean neon geometry."""
from __future__ import annotations

import base64
import io
import os
from PIL import Image, ImageDraw, ImageFilter
from . import poster as p
from .kickoff_team_names import short_name

W, H = 2000, 2500
WHITE = (255, 255, 255, 255)
TEXT = (28, 20, 22, 255)
RED = (190, 8, 18, 255)
NEON = (255, 36, 48, 255)
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
    """Keep the supplied background untouched; neon is never painted onto it."""
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
    return Image.new("RGBA", (W, H), (82, 0, 8, 255))


def _composite_local_glow(im, draw_fn, bounds, blur=8, pad=24):
    """Blur only a local crop around a neon shape, never the full canvas."""
    x0, y0, x1, y1 = map(int, bounds)
    pad = max(int(pad), int(blur * 3) + 4)
    cx0 = max(0, x0 - pad)
    cy0 = max(0, y0 - pad)
    cx1 = min(im.width, x1 + pad + 1)
    cy1 = min(im.height, y1 + pad + 1)
    local = Image.new("RGBA", (cx1 - cx0, cy1 - cy0), (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(local), cx0, cy0)
    im.alpha_composite(local.filter(ImageFilter.GaussianBlur(blur)), (cx0, cy0))


def _neon_outline(im, box, radius=38, glow_alpha=55, blur=8, width=3):
    """Premium neon frame: thin luminous edge, no dark drop shadow."""
    x0, y0, x1, y1 = map(int, box)

    def glow_line(gd, ox, oy):
        gd.rounded_rectangle((x0 - ox, y0 - oy, x1 - ox, y1 - oy),
                             radius=radius, outline=(255, 28, 42, glow_alpha),
                             width=width + 4)

    _composite_local_glow(im, glow_line, (x0, y0, x1, y1), blur=blur, pad=28)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((x0, y0, x1, y1), radius=radius,
                        outline=(255, 255, 255, 238), width=width)
    d.rounded_rectangle((x0 + 7, y0 + 7, x1 - 7, y1 - 7),
                        radius=max(8, radius - 7),
                        outline=(NEON[0], NEON[1], NEON[2], 180), width=2)


def _glass_card(im, box):
    x0, y0, x1, y1 = map(int, box)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((x0, y0, x1, y1), radius=40,
                        fill=(248, 247, 247, 232))
    _neon_outline(im, box, radius=40, glow_alpha=58, blur=8, width=4)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((x0 + 11, y0 + 11, x1 - 11, y1 - 11), radius=31,
                        outline=(255, 255, 255, 115), width=2)


def _date_tab(im, text, cy, width=650, height=82):
    d = ImageDraw.Draw(im)
    cx = W // 2
    x0, x1 = int(cx - width / 2), int(cx + width / 2)
    y0, y1 = int(cy - height / 2), int(cy + height / 2)
    pts = [(x0 + 34, y0), (x0 + 80, y0), (x0 + 102, y0 - 17),
           (x1 - 102, y0 - 17), (x1 - 80, y0), (x1 - 34, y0),
           (x1, y0 + 16), (x1, y1 - 16), (x1 - 34, y1),
           (x0 + 34, y1), (x0, y1 - 16), (x0, y0 + 16)]

    def glow_line(gd, ox, oy):
        shifted = [(x - ox, y - oy) for x, y in pts]
        gd.line(shifted + [shifted[0]], fill=(255, 30, 42, 65), width=8, joint="curve")

    _composite_local_glow(
        im, glow_line,
        (min(x for x, _ in pts), min(y for _, y in pts),
         max(x for x, _ in pts), max(y for _, y in pts)),
        blur=7, pad=24,
    )
    d.polygon(pts, fill=RED)
    d.line(pts + [pts[0]], fill=(255, 255, 255, 235), width=3, joint="curve")

    gx, gy, s = x0 + 52, int(cy), 24
    d.rounded_rectangle((gx - s, gy - s + 2, gx + s, gy + s),
                        radius=6, outline=WHITE, width=5)
    d.line((gx - s, gy - 5, gx + s, gy - 5), fill=WHITE, width=4)
    d.line((gx - 12, gy - s - 3, gx - 12, gy - 12), fill=WHITE, width=5)
    d.line((gx + 12, gy - s - 3, gx + 12, gy - 12), fill=WHITE, width=5)
    fs = p._fit_font(d, text, width - 118, 46, "Bold", min_size=28, rtl=True)
    p._draw_text(d, (cx + 24, cy), text, fs, "Bold", fill=WHITE,
                 anchor="mm", rtl=True)


def _time(im, text, cy, h=112):
    d = ImageDraw.Draw(im)
    w, sl = 320, 28
    cx = W // 2
    x0, x1 = cx - w // 2, cx + w // 2
    y0, y1 = int(cy - h / 2), int(cy + h / 2)
    poly = [(x0 + sl, y0), (x1 - sl, y0), (x1, cy),
            (x1 - sl, y1), (x0 + sl, y1), (x0, cy)]

    def glow_line(gd, ox, oy):
        shifted = [(x - ox, y - oy) for x, y in poly]
        gd.line(shifted + [shifted[0]], fill=(255, 28, 40, 70), width=6, joint="curve")

    _composite_local_glow(im, glow_line, (x0, y0, x1, y1), blur=6, pad=22)
    d.polygon(poly, fill=(187, 7, 18, 255))
    d.line(poly + [poly[0]], fill=(255, 255, 255, 245), width=4, joint="curve")
    d.line((x0 + sl + 14, y0 + 8, x1 - sl - 14, y0 + 8),
           fill=(255, 105, 112, 185), width=2)
    fs = p._fit_font(d, text, w - 32, 78, "ExtraBold", min_size=44,
                     rtl=False, role="time")
    p._draw_text(d, (cx, cy - 1), text, fs, "ExtraBold", fill=WHITE,
                 anchor="mm", rtl=False, role="time")


def _draw_team_name(d, name, center_x, cy, max_width, size):
    name = short_name(name)
    if not name:
        return
    fs = p._fit_font(d, name, max_width, size, "Bold", min_size=30, rtl=True)
    p._draw_text(d, (center_x, cy), name, fs, "Bold", fill=TEXT,
                 anchor="mm", rtl=True)


def _row(im, match, y0, y1):
    d = ImageDraw.Draw(im)
    cy = (y0 + y1) / 2
    rh = y1 - y0
    home, away = match.get("home") or {}, match.get("away") or {}
    logo = int(max(128, min(172, rh * .78)))
    for side, x in ((home, 1690), (away, 310)):
        try:
            path = p._logo_path(side.get("logo"), side.get("logo_dir", "logos"))
            p._paste_contained(im, path, x, cy, logo, logo)
        except Exception:
            pass

    # Fixed text columns keep every Arabic team name clear of the central time plate.
    # The Excel-approved two-word names are still applied by short_name().
    _draw_team_name(d, home.get("name_ar") or "", 1410, cy, 340,
                    int(max(38, min(52, rh * .27))))
    _draw_team_name(d, away.get("name_ar") or "", 590, cy, 340,
                    int(max(38, min(52, rh * .27))))
    _time(im, (match.get("time") or "16:30").strip(), cy,
          int(min(112, max(98, rh * .58))))


def _day(im, day, y, card_h, row_h):
    x0, x1 = 120, 1880
    card_y0, card_y1 = int(y + 34), int(y + card_h)
    _glass_card(im, (x0, card_y0, x1, card_y1))
    _date_tab(im, (day.get("date_label") or "").strip(), y + 34)

    matches = day.get("matches") or []
    top, bottom = card_y0 + 32, card_y1 - 18
    actual = (bottom - top) / max(1, len(matches))
    for i, m in enumerate(matches):
        a, b = top + i * actual, top + (i + 1) * actual
        if i:
            ImageDraw.Draw(im).line((x0 + 48, a, x1 - 48, a),
                                    fill=(185, 35, 42, 72), width=2)
        _row(im, m, a, b)


def render_kickoff(matchweek, days: list[dict], brand_logo=None,
                   background=None, scale=1.0):
    """Dynamic premium KICK OFF poster on a fixed native 2000x2500 canvas."""
    im = _bg(background)
    d = ImageDraw.Draw(im)
    try:
        p._paste_brand_logo(im, W / 2, 125, 205, 205, spec=brand_logo)
    except Exception:
        pass
    p._draw_text(d, (W / 2, 322), "KICK OFF", 178, "ExtraBold",
                 fill=WHITE, anchor="mm", rtl=False, role="time")
    label = (f"MATCHWEEK #{int(matchweek):02d}" if str(matchweek).isdigit()
             else f"MATCHWEEK {matchweek}")
    p._draw_text(d, (W / 2, 438), label, 72, "Bold", fill=WHITE,
                 anchor="mm", rtl=False, role="time")
    half = p._text_w(d, label, p._font(72, "Bold", "time"), rtl=False) / 2
    p._flank_lines(im, W / 2, 438, half, (255, 255, 255, 190),
                   ext=120, gap=26, width=3)

    days = [x for x in days if x.get("matches")]
    if not days:
        return im.convert("RGB")

    top, bottom = 520, 2390
    date_h, card_offset, inner_bottom, gap = 78, 30, 18, 16
    row_h = 188

    def stack_height(rh):
        return sum(date_h + card_offset + len(x.get("matches") or []) * rh + inner_bottom
                   for x in days) + max(0, len(days) - 1) * gap

    available = bottom - top
    total = stack_height(row_h)
    if total > available:
        row_h = max(168, int(row_h * available / total))
    total = stack_height(row_h)
    y = top + max(0, (available - total) / 2)

    for day in days:
        card_h = date_h + card_offset + len(day.get("matches") or []) * row_h + inner_bottom
        _day(im, day, y, card_h, row_h)
        y += card_h + gap

    if scale != 1.0:
        im = im.resize((int(W * scale), int(H * scale)), Image.LANCZOS)
    return im.convert("RGB")
