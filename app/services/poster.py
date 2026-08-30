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

# Pillow shapes and orders Arabic natively only when it is built with libraqm
# (HarfBuzz + FriBiDi). The official manylinux wheels bundle it, but a
# source-built Pillow (e.g. when the host resolves an unexpected Python
# version) does not — and then passing ``direction="rtl"`` raises. We detect
# the capability once and fall back to shaping the text ourselves, so the
# renderer produces correct Arabic on any host.
HAS_RAQM = features.check("raqm")

if not HAS_RAQM:  # pragma: no cover - depends on the host's Pillow build
    import arabic_reshaper
    from bidi.algorithm import get_display

    _RESHAPER = arabic_reshaper.ArabicReshaper(configuration={
        "delete_harakat": False,
        "support_ligatures": True,
        # Cairo maps isolated letters to their base codepoints rather than to
        # the Arabic Presentation Forms-B isolates, so ask for unshaped ones.
        "use_unshaped_instead_of_isolated": True,
    })


def _shape(text: str) -> str:
    """Return text ready to draw: untouched with libraqm, shaped without it."""
    if HAS_RAQM:
        return text
    return get_display(_RESHAPER.reshape(text))

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC = os.path.join(BASE_DIR, "static")
FONTS_DIR = os.path.join(STATIC, "fonts")

# The federation's faces are commercial and cannot be redistributed here, so
# they are picked up as drop-ins from app/static/fonts/. Two roles are used:
#   * "time"  -> kick-off times and the date bar   ("FWC2026")
#   * "text"  -> titles, club names, stadiums      ("YaModernPro-Bold")
# Either falls back to the bundled Cairo when its file is absent.
FALLBACK_FONT = "CairoVar.ttf"

_TIME_FONT_CANDIDATES = (
    # FWC2026 is the face used for kick-off times and the date bar.
    "FWC2026.otf", "FWC2026.ttf",
    "FWC2026-Bold.otf", "FWC2026-Bold.ttf",
    "FWC2026-Regular.otf", "FWC2026-Regular.ttf",
    "FWC 2026.otf", "FWC 2026.ttf",
    # Kept as a second choice so an existing drop-in still works.
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
# Back-compat alias used by the diagnostics endpoint.
FONT_PATH = TEXT_FONT_PATH
BG_PATH = os.path.join(STATIC, "img", "bg-vide.png")
LNFP_PATH = os.path.join(STATIC, "img", "logo-lnfp.png")
LIGUE1_PATH = os.path.join(STATIC, "img", "logo-ligue1.png")
LOGOS_DIR = os.path.join(STATIC, "logos")
TV_DIR = os.path.join(STATIC, "tv")

# Canvas is the native size of the BG template.
W, H = 2000, 2500

# Palette sampled from the reference poster. The design carries no gold: the
# accents are crystal white — glass highlights and translucent white edges.
WHITE = (255, 255, 255, 255)
CRYSTAL = (255, 255, 255, 235)       # accent text (the date line)
CRYSTAL_EDGE = (255, 255, 255, 90)   # hairline borders
BAR_FILL = (176, 12, 18, 235)        # glossy red bar (Ligue 1)
BAR_FILL_DARK = (128, 8, 12, 235)
BAR_FILL_L2 = (58, 61, 70, 235)      # charcoal bar (Ligue 2, matches its bg)
BAR_FILL_L2_DARK = (34, 36, 43, 235)
PANEL_FILL = (255, 255, 255, 26)     # centre panel behind the kick-off time


@lru_cache(maxsize=96)
def _font_file(path: str, size: int,
               weight: str = "Bold") -> ImageFont.FreeTypeFont:
    layout = ImageFont.Layout.RAQM if HAS_RAQM else ImageFont.Layout.BASIC
    f = ImageFont.truetype(path, size, layout_engine=layout)
    # Variable fonts expose named instances; a static face (such as a dropped-in
    # "Ya Modern Pro Bold") has none and is simply used as it comes.
    try:
        f.set_variation_by_name(weight)
    except Exception:
        pass
    return f


def _font(size: int, weight: str = "Bold",
          role: str = "text") -> ImageFont.FreeTypeFont:
    path = TIME_FONT_PATH if role == "time" else TEXT_FONT_PATH
    return _font_file(path, size, weight)


# Faces offered to the title picker. Only Arabic-capable files count (the
# numeric FWC2026 has no Arabic glyphs), and only ones actually present.
_TITLE_FONT_SOURCES = (
    ("modern", "Ya Modern Pro", TEXT_FONT_PATH),
    ("cairo", "Cairo", os.path.join(FONTS_DIR, FALLBACK_FONT)),
)
TITLE_FONTS = {fid: path for fid, _lbl, path in _TITLE_FONT_SOURCES
               if path and os.path.exists(path)}


def available_title_fonts() -> list[dict]:
    """Distinct title faces the studio may offer, in preference order."""
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
    """Keep Arabic off the numeric face.

    FWC2026 is a Latin/figures face with no Arabic glyphs, so anything with
    Arabic in it (the date bar, for instance) must be set in the text face or
    it would render as empty boxes. Kick-off times are digits only and stay on
    the numeric face.
    """
    if role == "time" and _ARABIC_RE.search(text or ""):
        return "text"
    return role


def _dir_kwargs(rtl: bool) -> dict:
    """``direction`` is only accepted when Pillow has libraqm."""
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
    """Shrink the font until the text fits inside ``max_w`` pixels."""
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
    """Break a club name onto at most two lines so it fits under its crest."""
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
    """Paste a club crest, adapted to the box, keeping aspect and colours."""
    if not logo_path or not os.path.exists(logo_path):
        return
    logo = _adapt_logo(Image.open(logo_path).convert("RGBA"), box_w, box_h)
    nw, nh = logo.size
    base.alpha_composite(logo, (int(cx - nw / 2), int(cy - nh / 2)))


def _open_brand_logo(spec: str | None):
    """Resolve the header logo.

    ``spec`` is either a file name inside ``static/img`` (a built-in
    competition badge) or a ``data:`` URL for a crest the user uploaded, so a
    new competition can be branded without redeploying. The artwork is always
    used with its own colours — never recoloured.
    """
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
    """Knock out a uniform background behind an opaque upload.

    Crests are routinely supplied as JPEG/PNG on a flat white (or single
    colour) plate. Pasting that verbatim drops an ugly rectangle onto the
    poster, so when the image carries no usable transparency we sample the
    four corners and, if they agree, make that colour transparent with a soft
    edge instead of a hard cut.
    """
    alpha = logo.getchannel("A")
    lo, _hi = alpha.getextrema()
    if lo < 250:
        return logo  # already has real transparency — trust it

    w, h = logo.size
    rgb = logo.convert("RGB")
    corners = [rgb.getpixel(p) for p in
               ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1))]
    ref = corners[0]
    spread = max(max(abs(c[i] - ref[i]) for i in range(3)) for c in corners)
    if spread > 26:
        return logo  # corners disagree: it is real artwork, not a plate

    px = np.asarray(rgb).astype(np.int16)
    dist = np.abs(px - np.array(ref, dtype=np.int16)).max(axis=2)
    dmax = float(dist.max())
    if dmax < 4:
        return logo  # a single flat colour: nothing to separate

    # Thresholds follow the image's own contrast. A crest printed in white on
    # a #f7f7f7 plate only spans ~8 levels, so fixed cut-offs would erase it,
    # while a colour crest on white spans the full range.
    near = max(2.0, dmax * 0.12)
    far = max(near + 2.0, dmax * 0.55)
    a = np.clip((dist - near) / (far - near), 0.0, 1.0)

    ink = a[a > 0.02]
    if ink.size < a.size * 0.0005:
        return logo  # extraction found almost nothing: keep the original

    # Normalise opacity so the strokes read as solid. Without this a crest
    # lifted off a low-contrast plate keeps the plate's faintness and appears
    # ghosted on the poster.
    ceiling = float(np.quantile(ink, 0.90))
    if ceiling > 0.02:
        a = np.clip(a / ceiling, 0.0, 1.0)
    out = np.dstack([px.astype(np.uint8), (a * 255).astype(np.uint8)])
    return Image.fromarray(out, "RGBA")


def _adapt_logo(logo: Image.Image, box_w: int, box_h: int) -> Image.Image:
    """Fit any supplied crest into the badge box, consistently and cleanly.

    Removes a flat backing plate, trims dead margins, then scales so the
    artwork fills the box optically. Colours are never altered.
    """
    logo = _strip_flat_background(logo)
    bbox = logo.getchannel("A").getbbox()
    if bbox:
        logo = logo.crop(bbox)
    lw, lh = logo.size
    if not lw or not lh:
        return logo
    # Wide marks would otherwise look tiny next to tall ones; normalise on the
    # dominant dimension so every crest reads at a similar visual weight.
    scale = min(box_w / lw, box_h / lh)
    nw, nh = max(1, round(lw * scale)), max(1, round(lh * scale))
    return logo.resize((nw, nh), Image.LANCZOS)


def _paste_brand_logo(base, cx, cy, box_w, box_h, spec=None):
    """Paste the competition badge, adapted to the box, colours untouched."""
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


# Ready-made title artwork (white lettering) dropped in from the "titre" set,
# used in auto mode; manual mode keeps the rendered text title.
TITLE_IMAGES = {"title-results.png", "title-fixtures.png", "title-ranking.png"}


def _paste_title_image(base, name, right_x, cy, max_w, max_h):
    """Paste a title graphic right-aligned at ``right_x``, centred on ``cy``.

    Returns the artwork's bottom edge (so the date line can sit under it), or
    ``None`` when the file is missing — the caller then falls back to text.
    """
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
    ``(:)`` or ``:)`` or ``():`` after the ground name.  Clean only those
    exact trailing placeholders at render time; legitimate parentheses
    inside a stadium name remain untouched.
    """
    text = str(value or "").strip()
    text = re.sub(r"\s*(?:\(\s*\)\s*:|\(\s*:\s*\)|:\)|\(:)\s*$", "", text)
    return text.strip()


def _stadium_glyph(h: int):
    """The supplied stadium illustration, scaled to ``h`` pixels tall."""
    art = _asset("icon-stadium.png")
    if art is None:
        return None
    w = max(1, round(art.width * h / art.height))
    return art.resize((w, max(1, h)), Image.LANCZOS)


def _stadium_icon(base, cx, cy, h=34):
    """Paste the stadium mark centred on ``(cx, cy)``."""
    glyph = _stadium_glyph(max(10, int(h)))
    if glyph is None:
        return
    base.alpha_composite(glyph, (int(cx - glyph.width / 2),
                                 int(cy - glyph.height / 2)))


def _glossy_bar(base, box, radius, dark=False):
    """The fixture bar: a glossy plate with a sheen and a hairline edge.

    Red for Ligue 1; a charcoal plate for Ligue 2, so the bars sit in the
    dark background instead of clashing with it. Drawn rather than composited
    from artwork: the supplied glass frame threw so much bloom across the
    middle that the ground name stopped being readable against it.
    """
    x0, y0, x1, y1 = (int(v) for v in box)
    w, h = x1 - x0, y1 - y0
    if w <= 0 or h <= 0:
        return

    fill = BAR_FILL_L2 if dark else BAR_FILL
    fill_dark = BAR_FILL_L2_DARK if dark else BAR_FILL_DARK
    sheen_amp = 24.0 if dark else 42.0

    # Vertical gradient, brightest just above the middle, so the plate reads as
    # curved glass. Built as an array — stacked rectangles leave visible steps.
    t = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, None]
    sheen = np.exp(-((t - 0.32) ** 2) / 0.045) * sheen_amp
    top = np.array(fill[:3], dtype=np.float32)
    bot = np.array(fill_dark[:3], dtype=np.float32)
    body = top + (bot - top) * t
    rgb = np.clip(body + sheen, 0, 255)
    strip = np.repeat(rgb[:, None, :], w, axis=1).astype(np.uint8)
    alpha = np.full((h, w, 1), fill[3], dtype=np.uint8)
    plate = Image.fromarray(np.concatenate([strip, alpha], axis=2), "RGBA")

    # Rounded-corner mask, then the highlights that sell the glass.
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
    """Parallelogram behind the kick-off time, edged with slanted glass rules."""
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    # Leaning right: the top edge sits further right than the bottom edge.
    lb, lt = cx - half_w, cx - half_w + slant
    rb, rt = cx + half_w, cx + half_w + slant
    d.polygon([(lb, y1), (lt, y0), (rt, y0), (rb, y1)], fill=PANEL_FILL)
    for xb, xt in ((lb, lt), (rb, rt)):
        d.line([(xb, y1), (xt, y0)], fill=CRYSTAL_EDGE, width=3)
    base.alpha_composite(layer)


@lru_cache(maxsize=24)
def _tv_glyph(h: int):
    """The TV mark that labels the broadcaster row, scaled to ``h`` px tall."""
    art = _asset("icon-tv.png")
    if art is None:
        return None
    w = max(1, round(art.width * h / art.height))
    return art.resize((w, max(1, h)), Image.LANCZOS)


@lru_cache(maxsize=64)
def _tv_raw(name: str):
    """A broadcaster mark at its native size (cached)."""
    path = os.path.join(TV_DIR, os.path.basename(name))
    if not os.path.exists(path):
        return None
    return Image.open(path).convert("RGBA")


@lru_cache(maxsize=16)
def _tv_combined_raw(name: str):
    """A ready multi-channel banner at its native size (cached)."""
    path = os.path.join(STATIC, "tv-combined", os.path.basename(name))
    if not os.path.exists(path):
        return None
    return Image.open(path).convert("RGBA")


def _draw_channels(base, logos, cx, cy, box_h, max_total_w, tv_x=None,
                   combined=None):
    """Lay the selected broadcaster marks in a centred row at ``cy``.

    The marks range from a wide banner to an upright badge, so every one is
    scaled to the *same optical area* — not a common height, which would let
    the widest one swamp the row — with a height clamp so an upright cannot
    tower over the rest. They then read at equal visual weight regardless of
    shape. The whole row is shrunk uniformly if it overflows the panel.

    ``combined`` is a ready banner for the picked set; when present (and the
    file exists) it is drawn as a single mark instead of the logos row.
    """
    tv = _tv_glyph(int(box_h * 1.7))
    icon_gap = int(box_h * 0.6)

    # Width available for the marks, centred on ``cx`` and kept clear of the
    # fixed TV icon, so a two- or three-logo row still sits in the middle.
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

    target_area = (box_h * 2.0) * box_h          # area of a 2:1 mark at box_h
    max_h = box_h * 1.35
    marks = []
    for m in raw:
        s = math.sqrt(target_area / (m.width * m.height))
        if m.height * s > max_h:                  # keep uprights in check
            s = max_h / m.height
        marks.append(m.resize((max(1, round(m.width * s)),
                               max(1, round(m.height * s))), Image.LANCZOS))

    gap = max(8, int(box_h * 0.5))
    total = sum(m.width for m in marks) + gap * (len(marks) - 1)
    if total > avail:                             # shrink the row to fit
        k = avail / total
        marks = [m.resize((max(1, round(m.width * k)),
                           max(1, round(m.height * k))), Image.LANCZOS)
                 for m in marks]
        gap = max(4, int(gap * k))
        total = sum(m.width for m in marks) + gap * (len(marks) - 1)

    x = cx - total / 2                            # centred on the panel
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
    """Render the finished poster as a Pillow image.

    ``matches`` items: {home:{name_ar,logo}, away:{name_ar,logo},
                        time, stadium_ar}
    ``brand_logo`` is a built-in badge file name or an uploaded ``data:`` URL.
    """
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

    # ---- header: competition badge (top-right), gold to match the brand ----
    _paste_brand_logo(base, cx=1560, cy=290, box_w=430, box_h=430,
                      spec=brand_logo)
    draw = ImageDraw.Draw(base)

    # ---- header: title. Auto mode drops in ready artwork; manual renders the
    #      typed text (with the chosen face and size, both clamped upstream). --
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

    # ---- date line ---------------------------------------------------------
    date_y = max(ty + 70, 690)
    dsize = _fit_font(draw, date_label, 1100, 62, "Bold")
    _draw_text(draw, (W / 2, date_y), date_label, dsize, "Bold",
               fill=CRYSTAL, anchor="mm")

    # ---- fixture bars ------------------------------------------------------
    matches = list(matches)
    n = max(1, len(matches))
    region_top = date_y + 96
    region_bot = 2430
    pitch = min(363.0, (region_bot - region_top) / n)
    bar_h = min(226.0, pitch * 0.58)
    bar_x0, bar_x1 = 336, W - 336          # the bar is inset; crests sit on it
    radius = int(bar_h * 0.20)
    cx_mid = W / 2

    # Centre the stack when a round has fewer fixtures than the page fits.
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

        # RTL: the home side sits on the right.
        home = m.get("home", {})
        away = m.get("away", {})
        crest = bar_h * 1.16                 # deliberately taller than the bar
        home_cx = bar_x1 - bar_h * 0.74
        away_cx = bar_x0 + bar_h * 0.74
        _paste_contained(base, _logo_path(home.get("logo"),
                                          home.get("logo_dir", "logos")),
                         home_cx, mid, crest, crest)
        _paste_contained(base, _logo_path(away.get("logo"),
                                          away.get("logo_dir", "logos")),
                         away_cx, mid, crest, crest)
        draw = ImageDraw.Draw(base)

        # Club names sit under the bar, wrapped to two lines when long.
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

        # Centre panel. In "results" mode it carries the final score alone;
        # otherwise the kick-off time, the ground and the broadcasters (the
        # stack shifts up and tightens when channels are present).
        if mode == "results":
            score = (m.get("score") or "0 - 0").strip()
            # Fill the gap between the two crests: as large as fits, so the
            # scoreline dominates the bar the way the reference poster does.
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

            # Both marks share one fixed column near the panel edge; the
            # stadium name and the channel logos stay centred on the panel.
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
    """Render a league standings poster, in the same visual language.

    ``rows`` items: {name_ar, logo, logo_dir, points, played}. Each club keeps
    its own ``played`` count (teams can differ). The order given is the order
    drawn — ranking is decided upstream (manual drag or a points sort).
    A "played" (لعب) column appears when any club has a non-zero count. When
    a table is split across pages, ``start_rank`` is the position of the first
    row so numbering stays continuous.
    """
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

    # ---- header: title (ready artwork or text) + league subtitle -----------
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

    # RTL column geometry: rank + crest on the right, the numeric columns on
    # the left (points, then a "played" column when one is supplied).
    rank_cx = bar_x1 - row_h * 0.58
    crest_cx = bar_x1 - row_h * 1.52
    pts_cx = bar_x0 + row_h * 0.80
    if show_played:
        played_cx = pts_cx + row_h * 1.45
        name_min_x = played_cx + row_h * 0.9
    else:
        played_cx = None
        name_min_x = pts_cx + row_h * 0.9
    name_x = crest_cx - row_h * 0.72          # right-anchored, grows left

    # Column captions just above the table — sized to read clearly.
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
