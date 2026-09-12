"""Compatibility patch for centering the standard poster header.

The title artwork and Ligue 1 logo are rendered as separate elements. Their
original anchors place the combined visual group too far to the right, so both
anchors are corrected together for results and fixtures posters.
"""
from . import poster

_original_paste_brand_logo = poster._paste_brand_logo
_original_paste_title_image = poster._paste_title_image


def _centered_brand_logo(base, cx, cy, box_w, box_h, spec=None):
    if cx == 1560 and box_w in (420, 430) and cy in (280, 290):
        cx = 1350
    return _original_paste_brand_logo(base, cx, cy, box_w, box_h, spec=spec)


def _centered_title_image(base, name, right_x, cy, max_w, max_h):
    if right_x == 1330 and cy in (290, 300):
        right_x = 1120
    return _original_paste_title_image(base, name, right_x, cy, max_w, max_h)


poster._paste_brand_logo = _centered_brand_logo
poster._paste_title_image = _centered_title_image
