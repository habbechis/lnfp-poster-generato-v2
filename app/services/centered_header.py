"""Compatibility patch for centering the standard poster header group.

The results and fixtures title assets have different intrinsic widths, so each
asset needs its own right anchor in order for the complete visible group to be
visually centered.
"""
from . import poster

_original_paste_brand_logo = poster._paste_brand_logo
_original_paste_title_image = poster._paste_title_image


def _centered_brand_logo(base, cx, cy, box_w, box_h, spec=None):
    if cx == 1560 and box_w in (420, 430) and cy in (280, 290):
        # Results and fixtures use different header heights; keep each logo
        # aligned with its corresponding title asset and center the full group.
        cx = 1510 if cy == 290 else 1430
    return _original_paste_brand_logo(base, cx, cy, box_w, box_h, spec=spec)


def _centered_title_image(base, name, right_x, cy, max_w, max_h):
    if right_x == 1330 and cy in (290, 300):
        asset_name = str(name or "").lower()
        if "fixture" in asset_name or "match" in asset_name:
            right_x = 1030
        else:
            right_x = 1280
    return _original_paste_title_image(base, name, right_x, cy, max_w, max_h)


poster._paste_brand_logo = _centered_brand_logo
poster._paste_title_image = _centered_title_image
