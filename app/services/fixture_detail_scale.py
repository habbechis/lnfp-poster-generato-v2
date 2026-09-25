"""Readable fixture-card details without enlarging stadium/TV icons.

The match bar is kept unchanged. Only the small information inside the
centre panel is improved:
- stadium text gets a modest size increase with width fitting;
- broadcaster marks are enlarged while the TV/stadium glyphs keep their
  original size;
- Diwan Sport receives an extra boost because its mark is particularly small;
- all enlarged marks are constrained to the centre-panel width.
"""
from __future__ import annotations

import math
import os

from PIL import Image

from . import poster


_original_draw_channels = poster._draw_channels
_original_fit_font = poster._fit_font
_original_tv_glyph = poster._tv_glyph
_original_tv_raw = poster._tv_raw


def _readable_draw_channels(base, logos, cx, cy, box_h, max_total_w,
                            tv_x=None, combined=None):
    """Enlarge broadcaster marks only; keep the TV icon at its normal size."""
    tv = _original_tv_glyph(int(box_h * 1.7))
    icon_gap = int(box_h * 0.6)

    if tv and tv_x is not None:
        half = (tv_x - tv.width / 2 - icon_gap) - cx
        avail = max(box_h, min(max_total_w, 2 * half))
    else:
        avail = max_total_w

    def _place_tv():
        if tv and tv_x is not None:
            base.alpha_composite(
                tv,
                (int(tv_x - tv.width / 2), int(cy - tv.height / 2)),
            )

    banner = poster._tv_combined_raw(combined) if combined else None
    if banner is not None:
        # Combined broadcaster artwork is enlarged moderately, but remains
        # constrained to the centre panel.
        target_h = box_h * 1.35
        s = min(avail / banner.width, target_h / banner.height)
        w = max(1, round(banner.width * s))
        h = max(1, round(banner.height * s))
        art = banner.resize((w, h), Image.LANCZOS)
        base.alpha_composite(art, (int(cx - w / 2), int(cy - h / 2)))
        _place_tv()
        return

    raw = [(name, _original_tv_raw(name)) for name in logos]
    raw = [(name, image) for name, image in raw if image]
    if not raw:
        _place_tv()
        return

    # Start from a larger target than the old renderer, but do not use the
    # enlarged value for the TV glyph above.
    target_box_h = box_h * 1.25
    target_area = (target_box_h * 2.0) * target_box_h
    max_h = target_box_h * 1.35

    marks = []
    for name, mark in raw:
        s = math.sqrt(target_area / (mark.width * mark.height))
        if mark.height * s > max_h:
            s = max_h / mark.height

        # Diwan Sport is the smallest-looking mark in the current Ligue 2
        # preview, so give only this broadcaster an additional 20% boost.
        if os.path.basename(name).lower() == "diwansport.png":
            s *= 1.20

        marks.append(
            (
                name,
                mark.resize(
                    (max(1, round(mark.width * s)),
                     max(1, round(mark.height * s))),
                    Image.LANCZOS,
                ),
            )
        )

    gap = max(8, int(box_h * 0.50))
    total = sum(m.width for _name, m in marks) + gap * (len(marks) - 1)

    # Never allow broadcaster marks to escape the centre panel.
    if total > avail:
        k = avail / total
        marks = [
            (
                name,
                m.resize(
                    (max(1, round(m.width * k)),
                     max(1, round(m.height * k))),
                    Image.LANCZOS,
                ),
            )
            for name, m in marks
        ]
        gap = max(4, int(gap * k))
        total = sum(m.width for _name, m in marks) + gap * (len(marks) - 1)

    x = cx - total / 2
    for i, (_name, mark) in enumerate(marks):
        base.alpha_composite(mark, (int(x), int(cy - mark.height / 2)))
        x += mark.width + (gap if i < len(marks) - 1 else 0)

    _place_tv()


def _readable_fit_font(draw, text, max_w, start_size, weight="Bold",
                       min_size=22, rtl=True, role="text", font_path=None):
    # Increase only the small fixture-detail labels. The original fit routine
    # still guarantees that the text stays inside its allocated width.
    if 200 <= max_w <= 360 and 18 <= start_size <= 36:
        start_size = int(round(start_size * 1.16))
    return _original_fit_font(
        draw, text, max_w, start_size, weight, min_size,
        rtl, role, font_path,
    )


poster._draw_channels = _readable_draw_channels
poster._fit_font = _readable_fit_font
