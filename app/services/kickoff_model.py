"""Premium 4:5 KICK OFF poster renderer with restrained neon treatment."""
from __future__ import annotations

import base64
import io
import os
from PIL import Image, ImageDraw, ImageFilter
from . import poster as p

W, H = 2000, 2500
WHITE = (255, 255, 255, 255)
TEXT = (28, 20, 22, 255)
RED = (198, 12, 22, 255)
NEON = (255, 42, 52, 255)
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


def _neon_round(im, box, radius=42, glow_alpha=125, blur=15, width=5):
    """Draw a clean red neon outline without the old black drop-shadow look."""
    x0, y0, x1, y1 = map(int, box)
    glow = Image.new("RGBA", im.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.rounded_rectangle((x0, y0, x1, y1), radius=radius,
                         outline=(255, 28, 40, glow_alpha), width=width + 8)
    glow = glow.filter(ImageFilter.GaussianBlur(blur))
    im.alpha_composite(glow)
    ImageDraw.Draw(im).rounded_rectangle(
        (x0, y0, x1, y1), radius=radius,
        outline=(255, 245, 245, 235), width=width
    )
    ImageDraw.Draw(im).rounded_rectangle(
        (x0 + 8, y0 + 8, x1 - 8, y1 - 8), radius=max(8, radius - 8),
        outline=(218, 25, 34, 150), width=2
    )


def _glass_card(im, box):
    x0, y0, x1, y1 = map(int, box)
    d = ImageDraw.Draw(im)
    # Frosted white panel with enough translucency to retain the red environment.
    d.rounded_rectangle((x0, y0, x1, y1), radius=42,
                        fill=(250, 248, 248, 224))
    _neon_round(im, (x0, y0, x1, y1), radius=42, glow_alpha=120, blur=16, width=5)
    d.rounded_rectangle((x0 + 12, y0 + 12, x1 - 12, y1 - 12), radius=32,
                        fill=(255, 255, 255, 16),
                        outline=(255, 255, 255, 100), width=2)


def _date_tab(im, text, cy, width=680, height=86):
    d = ImageDraw.Draw(im)
    cx = W // 2
    x0, x1 = int(cx - width / 2), int(cx + width / 2)
    y0, y1 = int(cy - height / 2), int(cy + height / 2)
    pts = [(x0 + 34, y0), (x0 + 82, y0), (x0 + 106, y0 - 18),
           (x1 - 106, y0 - 18), (x1 - 82, y0), (x1 - 34, y0),
           (x1, y0 + 17), (x1, y1 - 17), (x1 - 34, y1),
           (x0 + 34, y1), (x0, y1 - 17), (x0, y0 + 17)]
    d.polygon(pts, fill=RED)

    glow = Image.new("RGBA", im.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.line(pts + [pts[0]], fill=(255, 25, 35, 150), width=10, joint="curve")
    im.alpha_composite(glow.filter(ImageFilter.GaussianBlur(10)))
    d.line(pts + [pts[0]], fill=(255, 250, 250, 220), width=3, joint="curve")

    gx, gy, s = x0 + 58, int(cy), 25
    d.rounded_rectangle((gx - s, gy - s + 2, gx + s, gy + s),
                        radius=6, outline=WHITE, width=5)
    d.line((gx - s, gy - 5, gx + s, gy - 5), fill=WHITE, width=4)
    d.line((gx - 13, gy - s - 3, gx - 13, gy - 12), fill=WHITE, width=5)
    d.line((gx + 13, gy - s - 3, gx + 13, gy - 12), fill=WHITE, width=5)

    fs = p._fit_font(d, text, width - 135, 48, "Bold", min_size=29, rtl=True)
    p._draw_text(d, (cx + 28, cy), text, fs, "Bold", fill=WHITE,
                 anchor="mm", rtl=True)


def _time(im, text, cy, h=110):
    """Premium neon time capsule: red fill, crisp white edge, red glow only."""
    d = ImageDraw.Draw(im)
    w, sl = 330, 30
    cx = W // 2
    x0, x1 = cx - w // 2, cx + w // 2
    y0, y1 = int(cy - h / 2), int(cy + h / 2)
    poly = [(x0 + sl, y0), (x1 - sl, y0), (x1, cy),
            (x1 - sl, y1), (x0 + sl, y1), (x0, cy)]

    glow = Image.new("RGBA", im.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.polygon(poly, fill=(255, 20, 32, 150), outline=(255, 35, 45, 210), width=9)
    im.alpha_composite(glow.filter(ImageFilter.GaussianBlur(12)))

    d.polygon(poly, fill=(188, 8, 18, 255))
    d.line(poly + [poly[0]], fill=(255, 255, 255, 235), width=4, joint="curve")
    d.line((x0 + sl + 15, y0 + 9, x1 - sl - 15, y0 + 9),
           fill=(255, 105, 110, 180), width=3)

    fs = p._fit_font(d, text, w - 38, 78, "ExtraBold", min_size=43,
                     rtl=False, role="time")
    p._draw_text(d, (cx, cy - 1), text, fs, "ExtraBold", fill=WHITE,
                 anchor="mm", rtl=False, role="time")


def _row(im, match, y0, y1):
    d = ImageDraw.Draw(im)
    cy = (y0 + y1) / 2
    rh = y1 - y0
    logo = int(max(138, min(190, rh * .86)))
    home, away = match.get("home") or {}, match.get("away") or {}

    # Logos get a generous, consistent visual footprint.
    for side, x in ((home, 1690), (away, 310)):
        try:
            path = p._logo_path(side.get("logo"), side.get("logo_dir", "logos"))
            p._paste_contained(im, path, x, cy, logo, logo)
        except Exception:
            pass

    name_fs = int(max(39, min(55, rh * .29)))
    hn = (home.get("name_ar") or "").strip()
    an = (away.get("name_ar") or "").strip()
    if hn:
        fs = p._fit_font(d, hn, 365, name_fs, "Bold", min_size=30, rtl=True)
        p._draw_text(d, (1530, cy), hn, fs, "Bold", fill=TEXT, anchor="rm", rtl=True)
    if an:
        fs = p._fit_font(d, an, 365, name_fs, "Bold", min_size=30, rtl=True)
        p._draw_text(d, (470, cy), an, fs, "Bold", fill=TEXT, anchor="lm", rtl=True)

    # Minimal separators; no decorative chevrons competing with the time.
    _time(im, (match.get("time") or "16:30").strip(), cy,
          int(min(116, max(102, rh * .62))))


def _day(im, day, y, card_h, row_h):
    x0, x1 = 120, 1880
    card_y0, card_y1 = int(y + 38), int(y + card_h)
    _glass_card(im, (x0, card_y0, x1, card_y1))
    _date_tab(im, (day.get("date_label") or "").strip(), y + 38)

    matches = day.get("matches") or []
    top, bottom = card_y0 + 38, card_y1 - 22
    actual = (bottom - top) / max(1, len(matches))
    for i, m in enumerate(matches):
        a, b = top + i * actual, top + (i + 1) * actual
        if i:
            d = ImageDraw.Draw(im)
            d.line((x0 + 50, a, x1 - 50, a), fill=(190, 35, 40, 75), width=2)
        _row(im, m, a, b)


def render_kickoff(matchweek, days: list[dict], brand_logo=None,
                   background=None, scale=1.0):
    """Render the dynamic KICK OFF poster at native 2000x2500 (4:5)."""
    im = _bg(background)
    d = ImageDraw.Draw(im)

    # Header: deliberately separated so the logo never collides with KICK OFF.
    try:
        p._paste_brand_logo(im, W / 2, 126, 205, 205, spec=brand_logo)
    except Exception:
        pass

    p._draw_text(d, (W / 2, 326), "KICK OFF", 180, "ExtraBold",
                 fill=WHITE, anchor="mm", rtl=False, role="time")
    label = (f"MATCHWEEK #{int(matchweek):02d}" if str(matchweek).isdigit()
             else f"MATCHWEEK {matchweek}")
    p._draw_text(d, (W / 2, 448), label, 74, "Bold", fill=WHITE,
                 anchor="mm", rtl=False, role="time")
    half = p._text_w(d, label, p._font(74, "Bold", "time"), rtl=False) / 2
    p._flank_lines(im, W / 2, 448, half, (255, 255, 255, 190),
                   ext=135, gap=28, width=3)

    days = [x for x in days if x.get("matches")]
    if not days:
        return im.convert("RGB")

    # Fixed 4:5 fixture grid. Preserve readable rows; do not compress into a dashboard.
    top, bottom = 520, 2385
    date_h, card_offset, inner_bottom, gap = 82, 34, 22, 22
    row_h = 178

    def stack_height(rh):
        return sum(date_h + card_offset + len(x.get("matches") or []) * rh + inner_bottom
                   for x in days) + max(0, len(days) - 1) * gap

    available = bottom - top
    total = stack_height(row_h)
    if total > available:
        row_h = max(158, int(row_h * available / total))
    total = stack_height(row_h)
    y = top + max(0, (available - total) / 2)

    for day in days:
        card_h = date_h + card_offset + len(day.get("matches") or []) * row_h + inner_bottom
        _day(im, day, y, card_h, row_h)
        y += card_h + gap

    if scale != 1.0:
        im = im.resize((int(W * scale), int(H * scale)), Image.LANCZOS)
    return im.convert("RGB")
