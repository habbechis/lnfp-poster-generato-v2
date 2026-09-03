"""Poster generation service.

Composites the empty "BG vide" template into a finished match-day poster:
the LNFP logo, the Arabic title, the date bar and one card per fixture
(team logos, kick-off time and stadium). Rendered fully server-side with
Pillow + RAQM (HarfBuzz) so Arabic text is shaped and joined correctly and
the output needs no external image editor.
"""
from __future__ import annotations

import base64
import io
import math
import os
import re
from functools import lru_cache
from typing import Iterable

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, features

HAS_RAQM = features.check("raqm")

if not HAS_RAQM:  # pragma: no cover - depends on the host's Pillow build
    import arabic_reshaper
    from bidi.algorithm import get_display

    _RESHAPER = arabic_reshaper.ArabicReshaper(configuration={
        "delete_harakat": False,
        "support_ligatures": True,
        "use_unshaped_instead_of_isolated": True,
    })


def _shape(text: str) -> str:
    if HAS_RAQM:
        return text
    return get_display(_RESHAPER.reshape(text))

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC = os.path.join(BASE_DIR, "static")
FONTS_DIR = os.path.join(STATIC, "fonts")

FALLBACK_FONT = "CairoVar.ttf"

_TIME_FONT_CANDIDATES = (
    "FWC2026.otf", "FWC2026.ttf",
    "FWC2026-Bold.otf", "FWC2026-Bold.ttf",
    "FWC2026-Regular.otf", "FWC2026-Regular.ttf",
    "FWC 2026.otf", "FWC 2026.ttf",
    "Ya Modern Pro Bold.otf", "Ya Modern Pro Bold.ttf",
    "YaModernProBold.otf", "YaModernProBold.ttf",
)
_TEXT_FONT_CANDIDATES = (
    "YaModernPro-Bold.otf", "YaModernPro-Bold.ttf",
    "YaModernPro.otf", "YaModernPro.ttf",
)


def _resolve_font(candidates: tuple[str, ...], *env_vars: str) -> str:
    for var in env_vars:
        override = os.environ.get(var)
        if override:
            cand = (override if os.path.isabs(override)
                    else os.path.join(FONTS_DIR, override))
            if os.path.exists(cand):
                return cand
    for name in candidates:
        cand = os.path.join(FONTS_DIR, name)
        if os.path.exists(cand):
            return cand
    return os.path.join(FONTS_DIR, FALLBACK_FONT)


TEXT_FONT_PATH = _resolve_font(_TEXT_FONT_CANDIDATES,
                               "POSTER_FONT_TEXT", "POSTER_FONT")
TIME_FONT_PATH = _resolve_font(_TIME_FONT_CANDIDATES,
                               "POSTER_FONT_TIME", "POSTER_FONT")
FONT_PATH = TEXT_FONT_PATH
BG_PATH = os.path.join(STATIC, "img", "bg-vide.png")
KICKOFF_BG_PATH = os.path.join(STATIC, "img", "bg-kickoff.png")
LNFP_PATH = os.path.join(STATIC, "img", "logo-lnfp.png")
LIGUE1_PATH = os.path.join(STATIC, "img", "logo-ligue1.png")
LOGOS_DIR = os.path.join(STATIC, "logos")
TV_DIR = os.path.join(STATIC, "tv")

W, H = 2000, 2500

WHITE = (255, 255, 255, 255)
CRYSTAL = (255, 255, 255, 235)
CRYSTAL_EDGE = (255, 255, 255, 90)
BAR_FILL = (176, 12, 18, 235)
BAR_FILL_DARK = (128, 8, 12, 235)
BAR_FILL_L2 = (58, 61, 70, 235)
BAR_FILL_L2_DARK = (34, 36, 43, 235)
PANEL_FILL = (255, 255, 255, 26)


@lru_cache(maxsize=96)
def _font_file(path: str, size: int,
               weight: str = "Bold") -> ImageFont.FreeTypeFont:
    layout = ImageFont.Layout.RAQM if HAS_RAQM else ImageFont.Layout.BASIC
    f = ImageFont.truetype(path, size, layout_engine=layout)
    try:
        f.set_variation_by_name(weight)
    except Exception:
        pass
    return f


def _font(size: int, weight: str = "Bold",
          role: str = "text") -> ImageFont.FreeTypeFont:
    path = TIME_FONT_PATH if role == "time" else TEXT_FONT_PATH
    return _font_file(path, size, weight)


_TITLE_FONT_SOURCES = (
    ("modern", "Ya Modern Pro", TEXT_FONT_PATH),
    ("cairo", "Cairo", os.path.join(FONTS_DIR, FALLBACK_FONT)),
)
TITLE_FONTS = {fid: path for fid, _lbl, path in _TITLE_FONT_SOURCES
               if path and os.path.exists(path)}


def available_title_fonts() -> list[dict]:
    seen, out = set(), []
    for fid, lbl, path in _TITLE_FONT_SOURCES:
        if fid in TITLE_FONTS and path not in seen:
            seen.add(path)
            out.append({"id": fid, "label": lbl})
    return out


def title_font_path(fid: str | None) -> str | None:
    return TITLE_FONTS.get(fid or "")


_ARABIC_RE = re.compile(r"[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]")


def _role_for(text: str, role: str) -> str:
    if role == "time" and _ARABIC_RE.search(text or ""):
        return "text"
    return role


def _dir_kwargs(rtl: bool) -> dict:
    if not HAS_RAQM:
        return {}
    return {"direction": "rtl" if rtl else "ltr"}


def _text_w(draw: ImageDraw.ImageDraw, text: str, font, rtl=True) -> float:
    return draw.textlength(_shape(text), font=font, **_dir_kwargs(rtl))


def _draw_text(draw, xy, text, size, weight="Bold", fill=WHITE,
               anchor="mm", rtl=True, role="text", font_path=None):
    font = (_font_file(font_path, size, weight) if font_path
            else _font(size, weight, _role_for(text, role)))
    draw.text(xy, _shape(text), font=font, fill=fill, anchor=anchor,
              **_dir_kwargs(rtl))


def _fit_font(draw, text, max_w, start_size, weight="Bold", min_size=22,
              rtl=True, role="text", font_path=None):
    role = _role_for(text, role)
    size = start_size
    while size > min_size:
        font = (_font_file(font_path, size, weight) if font_path
                else _font(size, weight, role))
        if _text_w(draw, text, font, rtl) <= max_w:
            break
        size -= 2
    return size


def _wrap_to_width(draw, text, max_w, size, weight="Bold") -> list[str]:
    font = _font(size, weight)
    if _text_w(draw, text, font) <= max_w:
        return [text]
    words = text.split()
    best, best_diff = None, None
    for cut in range(1, len(words)):
        a, b = " ".join(words[:cut]), " ".join(words[cut:])
        wa, wb = _text_w(draw, a, font), _text_w(draw, b, font)
        if max(wa, wb) > max_w:
            continue
        diff = abs(wa - wb)
        if best_diff is None or diff < best_diff:
            best, best_diff = [a, b], diff
    return best or [text]


def _paste_contained(base, logo_path, cx, cy, box_w, box_h):
    if not logo_path or not os.path.exists(logo_path):
        return
    logo = _adapt_logo(Image.open(logo_path).convert("RGBA"), box_w, box_h)
    nw, nh = logo.size
    base.alpha_composite(logo, (int(cx - nw / 2), int(cy - nh / 2)))


def _open_brand_logo(spec: str | None):
    if not spec:
        spec = "logo-ligue1.png"
    if spec.startswith("data:"):
        try:
            _, _, b64 = spec.partition(",")
            return Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGBA")
        except Exception:
            return None
    path = os.path.join(STATIC, "img", os.path.basename(spec))
    if not os.path.exists(path):
        path = LIGUE1_PATH if os.path.exists(LIGUE1_PATH) else LNFP_PATH
    if not os.path.exists(path):
        return None
    return Image.open(path).convert("RGBA")


def _strip_flat_background(logo: Image.Image) -> Image.Image:
    alpha = logo.getchannel("A")
    lo, _hi = alpha.getextrema()
    if lo < 250:
        return logo

    w, h = logo.size
    rgb = logo.convert("RGB")
    corners = [rgb.getpixel(p) for p in
               ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1))]
    ref = corners[0]
    spread = max(max(abs(c[i] - ref[i]) for i in range(3)) for c in corners)
    if spread > 26:
        return logo

    px = np.asarray(rgb).astype(np.int16)
    dist = np.abs(px - np.array(ref, dtype=np.int16)).max(axis=2)
    dmax = float(dist.max())
    if dmax < 4:
        return logo

    near = max(2.0, dmax * 0.12)
    far = max(near + 2.0, dmax * 0.55)
    a = np.clip((dist - near) / (far - near), 0.0, 1.0)

    ink = a[a > 0.02]
    if ink.size < a.size * 0.0005:
        return logo

    ceiling = float(np.quantile(ink, 0.90))
    if ceiling > 0.02:
        a = np.clip(a / ceiling, 0.0, 1.0)
    out = np.dstack([px.astype(np.uint8), (a * 255).astype(np.uint8)])
    return Image.fromarray(out, "RGBA")


def _adapt_logo(logo: Image.Image, box_w: int, box_h: int) -> Image.Image:
    logo = _strip_flat_background(logo)
    bbox = logo.getchannel("A").getbbox()
    if bbox:
        logo = logo.crop(bbox)
    lw, lh = logo.size
    if not lw or not lh:
        return logo
    scale = min(box_w / lw, box_h / lh)
    nw, nh = max(1, round(lw * scale)), max(1, round(lh * scale))
    return logo.resize((nw, nh), Image.LANCZOS)


def _paste_brand_logo(base, cx, cy, box_w, box_h, spec=None):
    logo = _open_brand_logo(spec)
    if logo is None:
        return
    logo = _adapt_logo(logo, box_w, box_h)
    nw, nh = logo.size
    base.alpha_composite(logo, (int(cx - nw / 2), int(cy - nh / 2)))


@lru_cache(maxsize=8)
def _asset(name: str):
    path = os.path.join(STATIC, "img", name)
    if not os.path.exists(path):
        return None
    return Image.open(path).convert("RGBA")


TITLE_IMAGES = {"title-results.png", "title-fixtures.png", "title-ranking.png"}


def _paste_title_image(base, name, right_x, cy, max_w, max_h):
    art = _asset(os.path.basename(name))
    if art is None:
        return None
    scale = min(max_w / art.width, max_h / art.height)
    w, h = max(1, round(art.width * scale)), max(1, round(art.height * scale))
    art = art.resize((w, h), Image.LANCZOS)
    x, y = right_x - w, cy - h / 2
    base.alpha_composite(art, (int(x), int(y)))
    return y + h


@lru_cache(maxsize=24)
def _clean_stadium_display(value) -> str:
    """Remove stray punctuation accidentally carried into stadium labels.

    Some pasted/PDF-derived fixture rows can append the old placeholder
    ``(:)``, ``:)`` or ``():`` after the ground name. Clean only those exact
    trailing placeholders at render time; legitimate parentheses inside a
    stadium name remain untouched.
    """
    text = str(value or "").strip()
    text = re.sub(r"\s*(?:\(\s*\)\s*:|\(\s*:\s*\)|:\)|\(:)\s*$", "", text)
    return text.strip()


def _stadium_glyph(h: int):
    art = _asset("icon-stadium.png")
    if art is None:
        return None
    w = max(1, round(art.width * h / art.height))
    return art.resize((w, max(1, h)), Image.LANCZOS)


def _stadium_icon(base, cx, cy, h=34):
    glyph = _stadium_glyph(max(10, int(h)))
    if glyph is None:
        return
    base.alpha_composite(glyph, (int(cx - glyph.width / 2),
                                 int(cy - glyph.height / 2)))


def _glossy_bar(base, box, radius, dark=False):
    x0, y0, x1, y1 = (int(v) for v in box)
    w, h = x1 - x0, y1 - y0
    if w <= 0 or h <= 0:
        return

    fill = BAR_FILL_L2 if dark else BAR_FILL
    fill_dark = BAR_FILL_L2_DARK if dark else BAR_FILL_DARK
    sheen_amp = 24.0 if dark else 42.0

    t = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, None]
    sheen = np.exp(-((t - 0.32) ** 2) / 0.045) * sheen_amp
    top = np.array(fill[:3], dtype=np.float32)
    bot = np.array(fill_dark[:3], dtype=np.float32)
    body = top + (bot - top) * t
    rgb = np.clip(body + sheen, 0, 255)
    strip = np.repeat(rgb[:, None, :], w, axis=1).astype(np.uint8)
    alpha = np.full((h, w, 1), fill[3], dtype=np.uint8)
    plate = Image.fromarray(np.concatenate([strip, alpha], axis=2), "RGBA")

    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1),
                                           radius=radius, fill=255)
    plate.putalpha(Image.composite(plate.getchannel("A"),
                                   Image.new("L", (w, h), 0), mask))
    d = ImageDraw.Draw(plate)
    d.line([(radius, 2), (w - radius, 2)], fill=(255, 255, 255, 85), width=3)
    d.rounded_rectangle((1, 1, w - 2, h - 2), radius=radius,
                        outline=CRYSTAL_EDGE, width=3)
    base.alpha_composite(plate, (x0, y0))


def _centre_panel(base, cx, y0, y1, half_w, slant):
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    lb, lt = cx - half_w, cx - half_w + slant
    rb, rt = cx + half_w, cx + half_w + slant
    d.polygon([(lb, y1), (lt, y0), (rt, y0), (rb, y1)], fill=PANEL_FILL)
    for xb, xt in ((lb, lt), (rb, rt)):
        d.line([(xb, y1), (xt, y0)], fill=CRYSTAL_EDGE, width=3)
    base.alpha_composite(layer)


@lru_cache(maxsize=24)
def _tv_glyph(h: int):
    art = _asset("icon-tv.png")
    if art is None:
        return None
    w = max(1, round(art.width * h / art.height))
    return art.resize((w, max(1, h)), Image.LANCZOS)


@lru_cache(maxsize=64)
def _tv_raw(name: str):
    path = os.path.join(TV_DIR, os.path.basename(name))
    if not os.path.exists(path):
        return None
    return Image.open(path).convert("RGBA")


@lru_cache(maxsize=16)
def _tv_combined_raw(name: str):
    path = os.path.join(STATIC, "tv-combined", os.path.basename(name))
    if not os.path.exists(path):
        return None
    return Image.open(path).convert("RGBA")


def _draw_channels(base, logos, cx, cy, box_h, max_total_w, tv_x=None,
                   combined=None):
    tv = _tv_glyph(int(box_h * 1.7))
    icon_gap = int(box_h * 0.6)

    if tv and tv_x is not None:
        half = (tv_x - tv.width / 2 - icon_gap) - cx
        avail = max(box_h, min(max_total_w, 2 * half))
    else:
        avail = max_total_w

    def _place_tv():
        if tv and tv_x is not None:
            base.alpha_composite(tv, (int(tv_x - tv.width / 2),
                                      int(cy - tv.height / 2)))

    banner = _tv_combined_raw(combined) if combined else None
    if banner is not None:
        s = min(avail / banner.width, (box_h * 1.8) / banner.height)
        w, h = max(1, round(banner.width * s)), max(1, round(banner.height * s))
        art = banner.resize((w, h), Image.LANCZOS)
        base.alpha_composite(art, (int(cx - w / 2), int(cy - h / 2)))
        _place_tv()
        return

    raw = [m for m in (_tv_raw(n) for n in logos) if m]
    if not raw:
        return

    target_area = (box_h * 2.0) * box_h
    max_h = box_h * 1.35
    marks = []
    for m in raw:
        s = math.sqrt(target_area / (m.width * m.height))
        if m.height * s > max_h:
            s = max_h / m.height
        marks.append(m.resize((max(1, round(m.width * s)),
                               max(1, round(m.height * s))), Image.LANCZOS))

    gap = max(8, int(box_h * 0.5))
    total = sum(m.width for m in marks) + gap * (len(marks) - 1)
    if total > avail:
        k = avail / total
        marks = [m.resize((max(1, round(m.width * k)),
                           max(1, round(m.height * k))), Image.LANCZOS)
                 for m in marks]
        gap = max(4, int(gap * k))
        total = sum(m.width for m in marks) + gap * (len(marks) - 1)

    x = cx - total / 2
    for i, m in enumerate(marks):
        base.alpha_composite(m, (int(x), int(cy - m.height / 2)))
        x += m.width + (gap if i < len(marks) - 1 else 0)
    _place_tv()


def _logo_path(logo: str | None, folder: str = "logos") -> str | None:
    if not logo:
        return None
    return os.path.join(STATIC, os.path.basename(folder), os.path.basename(logo))


def render_poster(title: str, date_label: str, matches: Iterable[dict],
                  brand_logo: str | None = None,
                  background: str | None = None,
                  title_size: float = 1.0,
                  title_font: str | None = None,
                  title_image: str | None = None,
                  mode: str = "fixtures",
                  scale: float = 1.0) -> Image.Image:
    bg_path = BG_PATH
    if background:
        cand = os.path.join(STATIC, "img", os.path.basename(background))
        if os.path.exists(cand):
            bg_path = cand
    dark = bool(background) and "ligue2" in os.path.basename(background)
    base = Image.open(bg_path).convert("RGBA")
    if base.size != (W, H):
        base = base.resize((W, H), Image.LANCZOS)
    draw = ImageDraw.Draw(base)

    _paste_brand_logo(base, cx=1560, cy=290, box_w=430, box_h=430,
                      spec=brand_logo)
    draw = ImageDraw.Draw(base)

    ty = 150
    bottom = None
    if title_image:
        bottom = _paste_title_image(base, title_image, right_x=1330, cy=300,
                                    max_w=1160, max_h=380)
    if bottom is not None:
        ty = int(bottom) + 24
    else:
        tfont = title_font_path(title_font)
        tscale = title_size if 0.4 <= (title_size or 0) <= 2.0 else 1.0
        title_lines = [ln for ln in title.split("\n") if ln.strip()]
        right_x = 1330
        for i, line in enumerate(title_lines):
            size = int((96 if i == 0 else 88) * tscale)
            size = _fit_font(draw, line, 1220, size, "ExtraBold",
                             font_path=tfont)
            _draw_text(draw, (right_x, ty), line, size, "ExtraBold",
                       fill=WHITE, anchor="ra", font_path=tfont)
            ty += int(size * 1.28)

    date_y = max(ty + 70, 690)
    dsize = _fit_font(draw, date_label, 1100, 62, "Bold")
    _draw_text(draw, (W / 2, date_y), date_label, dsize, "Bold",
               fill=CRYSTAL, anchor="mm")

    matches = list(matches)
    n = max(1, len(matches))
    region_top = date_y + 96
    region_bot = 2430
    pitch = min(363.0, (region_bot - region_top) / n)
    bar_h = min(226.0, pitch * 0.58)
    bar_x0, bar_x1 = 336, W - 336
    radius = int(bar_h * 0.20)
    cx_mid = W / 2

    block_h = pitch * n
    region_top += max(0, (region_bot - region_top - block_h) / 2)

    for i, m in enumerate(matches):
        top = region_top + i * pitch
        y0, y1 = top, top + bar_h
        mid = (y0 + y1) / 2

        _glossy_bar(base, (bar_x0, y0, bar_x1, y1), radius, dark=dark)
        _centre_panel(base, cx_mid, y0 + 5, y1 - 5,
                      half_w=bar_h * 1.24, slant=bar_h * 0.12)
        draw = ImageDraw.Draw(base)

        home = m.get("home", {})
        away = m.get("away", {})
        crest = bar_h * 1.16
        home_cx = bar_x1 - bar_h * 0.74
        away_cx = bar_x0 + bar_h * 0.74
        _paste_contained(base, _logo_path(home.get("logo"),
                                          home.get("logo_dir", "logos")),
                         home_cx, mid, crest, crest)
        _paste_contained(base, _logo_path(away.get("logo"),
                                          away.get("logo_dir", "logos")),
                         away_cx, mid, crest, crest)
        draw = ImageDraw.Draw(base)

        name_y = y1 + bar_h * 0.34
        for cx, team in ((home_cx, home), (away_cx, away)):
            name = (team.get("name_ar") or "").strip()
            if not name:
                continue
            nsize = int(min(40, bar_h * 0.175))
            lines = _wrap_to_width(draw, name, 520, nsize, "Bold")
            ly = name_y - (len(lines) - 1) * nsize * 0.62
            for line in lines:
                _draw_text(draw, (cx, ly), line, nsize, "Bold",
                           fill=WHITE, anchor="mm")
                ly += nsize * 1.24

        if mode == "results":
            score = (m.get("score") or "0 - 0").strip()
            inner = (home_cx - crest / 2) - (away_cx + crest / 2)
            ssize = _fit_font(draw, score, inner * 0.94, int(bar_h * 0.98),
                              "ExtraBold", min_size=48, rtl=False, role="time")
            _draw_text(draw, (cx_mid, mid), score, ssize,
                       "ExtraBold", fill=WHITE, anchor="mm", rtl=False,
                       role="time")
        else:
            channels = m.get("channels") or []
            time_text = m.get("time", "16:30")
            tsize = int(bar_h * (0.42 if channels else 0.48))
            time_y = mid - bar_h * (0.20 if channels else 0.06)
            _draw_text(draw, (cx_mid, time_y), time_text,
                       tsize, "ExtraBold", fill=WHITE, anchor="mm", rtl=False,
                       role="time")

            icon_col = cx_mid + bar_h * 1.02
            stadium = _clean_stadium_display(m.get("stadium_ar"))
            if stadium:
                ssize = int(min(34, bar_h * 0.15))
                sy = mid + bar_h * (0.08 if channels else 0.28)
                ssize = _fit_font(draw, stadium, bar_h * 1.55, ssize,
                                  "SemiBold", min_size=18)
                _draw_text(draw, (cx_mid, sy), stadium, ssize,
                           "SemiBold", fill=WHITE, anchor="mm")
                _stadium_icon(base, icon_col, sy, h=ssize * 1.42)

            combined = m.get("channels_combined")
            if channels or combined:
                _draw_channels(base, channels, cx_mid, mid + bar_h * 0.33,
                               box_h=bar_h * 0.17, max_total_w=bar_h * 2.5,
                               tv_x=icon_col, combined=combined)
                draw = ImageDraw.Draw(base)

    if scale != 1.0:
        base = base.resize((int(W * scale), int(H * scale)), Image.LANCZOS)
    return base.convert("RGB")


def render_standings(title: str, subtitle: str, rows: Iterable[dict],
                     brand_logo: str | None = None,
                     background: str | None = None,
                     title_image: str | None = None,
                     start_rank: int = 1,
                     scale: float = 1.0) -> Image.Image:
    bg_path = BG_PATH
    if background:
        cand = os.path.join(STATIC, "img", os.path.basename(background))
        if os.path.exists(cand):
            bg_path = cand
    dark = bool(background) and "ligue2" in os.path.basename(background)
    base = Image.open(bg_path).convert("RGBA")
    if base.size != (W, H):
        base = base.resize((W, H), Image.LANCZOS)
    draw = ImageDraw.Draw(base)

    _paste_brand_logo(base, cx=1560, cy=280, box_w=420, box_h=420,
                      spec=brand_logo)
    draw = ImageDraw.Draw(base)

    ty, right_x = 150, 1330
    bottom = _paste_title_image(base, title_image, right_x=1330, cy=290,
                                max_w=1160, max_h=360) if title_image else None
    if bottom is not None:
        ty = int(bottom) + 20
    else:
        tsize = _fit_font(draw, title, 1180, 100, "ExtraBold")
        _draw_text(draw, (right_x, ty), title, tsize, "ExtraBold",
                   fill=WHITE, anchor="ra")
        ty += int(tsize * 1.24)
    if subtitle:
        s2 = _fit_font(draw, subtitle, 1120, 58, "Bold")
        _draw_text(draw, (right_x, ty), subtitle, s2, "Bold",
                   fill=CRYSTAL, anchor="ra")
        ty += int(s2 * 1.2)

    rows = list(rows)
    n = max(1, len(rows))
    show_played = any(r.get("played") for r in rows)
    region_top = max(ty + 120, 720)
    region_bot = 2430
    pitch = (region_bot - region_top) / n
    row_h = min(200.0, pitch * 0.82)
    bar_x0, bar_x1 = 250, W - 250
    radius = int(row_h * 0.22)

    rank_cx = bar_x1 - row_h * 0.58
    crest_cx = bar_x1 - row_h * 1.52
    pts_cx = bar_x0 + row_h * 0.80
    if show_played:
        played_cx = pts_cx + row_h * 1.45
        name_min_x = played_cx + row_h * 0.9
    else:
        played_cx = None
        name_min_x = pts_cx + row_h * 0.9
    name_x = crest_cx - row_h * 0.72

    hy = region_top - 60
    cap = 46
    _draw_text(draw, (name_x, hy), "الفريق", cap, "Bold", fill=WHITE,
               anchor="rm")
    _draw_text(draw, (pts_cx, hy), "نقاط", cap, "Bold", fill=WHITE,
               anchor="mm")
    if show_played:
        _draw_text(draw, (played_cx, hy), "لعب", cap, "Bold", fill=WHITE,
                   anchor="mm")

    for i, r in enumerate(rows):
        top = region_top + i * pitch + (pitch - row_h) / 2
        y0, y1 = top, top + row_h
        mid = (y0 + y1) / 2
        _glossy_bar(base, (bar_x0, y0, bar_x1, y1), radius, dark=dark)
        draw = ImageDraw.Draw(base)

        _draw_text(draw, (rank_cx, mid), str(start_rank + i),
                   int(row_h * 0.46), "ExtraBold", fill=WHITE, anchor="mm",
                   rtl=False, role="time")
        _paste_contained(base, _logo_path(r.get("logo"),
                                          r.get("logo_dir", "logos")),
                         crest_cx, mid, row_h * 1.04, row_h * 1.04)
        draw = ImageDraw.Draw(base)

        name = (r.get("name_ar") or "").strip()
        if name:
            nsize = _fit_font(draw, name, name_x - name_min_x,
                              int(row_h * 0.34), "Bold", min_size=20)
            _draw_text(draw, (name_x, mid), name, nsize, "Bold",
                       fill=WHITE, anchor="rm")

        pts = str(r.get("points", 0))
        _draw_text(draw, (pts_cx, mid), pts, int(row_h * 0.56), "ExtraBold",
                   fill=WHITE, anchor="mm", rtl=False, role="time")
        if show_played:
            _draw_text(draw, (played_cx, mid), str(r.get("played", 0)),
                       int(row_h * 0.50), "ExtraBold", fill=CRYSTAL,
                       anchor="mm", rtl=False, role="time")

    if scale != 1.0:
        base = base.resize((int(W * scale), int(H * scale)), Image.LANCZOS)
    return base.convert("RGB")


# --------------------------------------------------------------------------- #
# KICK OFF poster — round preview, white-card style
# --------------------------------------------------------------------------- #
CARD_FILL = (250, 250, 251, 255)
CARD_GLOW = (200, 20, 24, 100)
NAME_DARK = (24, 28, 48, 255)
DATE_RED = (176, 12, 18, 255)


def _white_card(base, box, radius, blur=14):
    """A white card with a thin red border and a soft red glow — matches the
    reference KICK OFF poster (red-tinted halo bleeding onto the red page)."""
    x0, y0, x1, y1 = (int(v) for v in box)
    w, h = x1 - x0, y1 - y0
    if w <= 0 or h <= 0:
        return
    pad = blur * 3

    glow = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    ImageDraw.Draw(glow).rounded_rectangle(
        (pad, pad, pad + w, pad + h), radius=radius, fill=CARD_GLOW)
    glow = glow.filter(ImageFilter.GaussianBlur(blur))
    base.alpha_composite(glow, (x0 - pad, y0 - pad))

    card = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(card).rounded_rectangle((0, 0, w - 1, h - 1), radius=radius,
                                           fill=CARD_FILL)
    base.alpha_composite(card, (x0, y0))

    d = ImageDraw.Draw(base)
    d.rounded_rectangle((x0, y0, x1 - 1, y1 - 1), radius=radius,
                        outline=DATE_RED, width=4)


def _kickoff_time_pill(base, cx, cy, text, h=70):
    draw = ImageDraw.Draw(base)
    size = int(h * 0.5)
    tw = _text_w(draw, text, _font(size, "ExtraBold", "time"), rtl=False)
    w = max(h * 1.9, tw + h * 0.8)
    box = (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
    _glossy_bar(base, box, radius=int(h / 2), dark=False)
    draw = ImageDraw.Draw(base)
    _draw_text(draw, (cx, cy - h * 0.03), text, size, "ExtraBold", fill=WHITE,
              anchor="mm", rtl=False, role="time")
    chev = int(h * 0.5)
    _draw_text(draw, (cx - w / 2 - chev * 0.9, cy), "\u00ab", chev, "Bold",
              fill=(255, 255, 255, 235), anchor="mm", rtl=False)
    _draw_text(draw, (cx + w / 2 + chev * 0.9, cy), "\u00bb", chev, "Bold",
              fill=(255, 255, 255, 235), anchor="mm", rtl=False)



def _flank_lines(base, cx, cy, text_half_w, color, ext=90, gap=26, width=3):
    """Two short rules flanking centred text — the reference's separator style."""
    d = ImageDraw.Draw(base)
    l0 = cx - text_half_w - gap
    l1 = l0 - ext
    r0 = cx + text_half_w + gap
    r1 = r0 + ext
    d.line([(l1, cy), (l0, cy)], fill=color, width=width)
    d.line([(r0, cy), (r1, cy)], fill=color, width=width)

def render_kickoff(matchweek, days: list[dict],
                   brand_logo: str | None = None,
                   background: str | None = None,
                   scale: float = 1.0) -> Image.Image:
    bg_path = KICKOFF_BG_PATH if os.path.exists(KICKOFF_BG_PATH) else BG_PATH
    if background:
        cand = os.path.join(STATIC, "img", os.path.basename(background))
        if os.path.exists(cand):
            bg_path = cand
    base = Image.open(bg_path).convert("RGBA")
    if base.size != (W, H):
        base = base.resize((W, H), Image.LANCZOS)
    draw = ImageDraw.Draw(base)

    cy = 230
    _paste_brand_logo(base, cx=W / 2, cy=cy, box_w=210, box_h=210,
                      spec=brand_logo)
    draw = ImageDraw.Draw(base)
    ty = cy + 150
    _draw_text(draw, (W / 2, ty), "KICK OFF", 128, "ExtraBold",
              fill=WHITE, anchor="mm", rtl=False, role="time")
    ty += 96
    label = f"MATCHWEEK #{int(matchweek):02d}" if str(matchweek).isdigit() \
        else f"MATCHWEEK {matchweek}"
    _draw_text(draw, (W / 2, ty), label, 62, "Bold",
              fill=CRYSTAL, anchor="mm", rtl=False, role="time")
    mw_half_w = _text_w(draw, label, _font(62, "Bold", "time"), rtl=False) / 2
    _flank_lines(base, W / 2, ty, mw_half_w, CRYSTAL_EDGE, ext=70, gap=24,
                width=3)
    draw = ImageDraw.Draw(base)
    content_top = ty + 70

    days = [d for d in days if d.get("matches")]
    n_matches = sum(len(d["matches"]) for d in days)
    n_days = max(1, len(days))
    region_top, region_bot = content_top + 40, 2440
    avail = region_bot - region_top

    day_hdr_h = 70
    card_gap = 26
    row_gap = 2
    card_pad = 6

    def _total_h(row_h):
        return (n_days * day_hdr_h + n_matches * row_h
                + (n_matches - n_days) * row_gap
                + n_days * card_pad * 2 + (n_days - 1) * card_gap)

    row_h = 150.0
    while row_h > 70 and _total_h(row_h) > avail:
        row_h -= 4
    day_hdr_h = min(day_hdr_h, max(44, day_hdr_h * (row_h / 150.0)))

    y = region_top + max(0, (avail - _total_h(row_h)) / 2)
    crest = row_h * 0.82
    name_size = int(min(34, row_h * 0.20))
    time_h = min(70, row_h * 0.44)

    for day in days:
        dsize = int(min(44, day_hdr_h * 0.6))
        date_label = day.get("date_label", "")
        line_y = y + day_hdr_h / 2
        _draw_text(draw, (W / 2, line_y), date_label, dsize, "Bold",
                  fill=DATE_RED, anchor="mm")
        half_w = _text_w(draw, date_label, _font(dsize, "Bold")) / 2
        _flank_lines(base, W / 2, line_y, half_w, DATE_RED, ext=110, gap=30,
                    width=3)
        draw = ImageDraw.Draw(base)
        y += day_hdr_h

        matches = day["matches"]
        card_h = (len(matches) * row_h + (len(matches) - 1) * row_gap
                 + card_pad * 2)
        card_box = (140, y, W - 140, y + card_h)
        _white_card(base, card_box, radius=int(row_h * 0.22))
        draw = ImageDraw.Draw(base)

        ry = y + card_pad
        for i, m in enumerate(matches):
            mid = ry + row_h / 2
            home, away = m.get("home", {}), m.get("away", {})
            home_cx = (W - 280) * 0.80 + 140
            away_cx = (W - 280) * 0.20 + 140
            time_cx = W / 2

            _paste_contained(base, _logo_path(home.get("logo"),
                                              home.get("logo_dir", "logos")),
                             home_cx, mid, crest, crest)
            _paste_contained(base, _logo_path(away.get("logo"),
                                              away.get("logo_dir", "logos")),
                             away_cx, mid, crest, crest)
            draw = ImageDraw.Draw(base)

            for cx, team, anchor in ((home_cx, home, "right"),
                                     (away_cx, away, "left")):
                name = (team.get("name_ar") or "").strip()
                if not name:
                    continue
                gap = crest / 2 + 22
                tx = cx - gap if anchor == "right" else cx + gap
                a = "rm" if anchor == "right" else "lm"
                nsize = _fit_font(draw, name, 320, name_size, "Bold",
                                  min_size=18)
                _draw_text(draw, (tx, mid), name, nsize, "Bold",
                          fill=NAME_DARK, anchor=a)

            _kickoff_time_pill(base, time_cx, mid, m.get("time", "16:30"),
                               h=time_h)
            draw = ImageDraw.Draw(base)

            ry += row_h
            if i < len(matches) - 1:
                dl = ImageDraw.Draw(base)
                dl.line([(200, ry + row_gap / 2), (W - 200, ry + row_gap / 2)],
                       fill=(0, 0, 0, 30), width=2)
                ry += row_gap

        y += card_h + card_gap

    if scale != 1.0:
        base = base.resize((int(W * scale), int(H * scale)), Image.LANCZOS)
    return base.convert("RGB")


# --------------------------------------------------------------------------- #
# PNG byte helpers
# --------------------------------------------------------------------------- #
def render_png_bytes(*args, **kwargs) -> bytes:
    img = render_poster(*args, **kwargs)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def render_standings_png_bytes(*args, **kwargs) -> bytes:
    img = render_standings(*args, **kwargs)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def render_kickoff_png_bytes(*args, **kwargs) -> bytes:
    img = render_kickoff(*args, **kwargs)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
