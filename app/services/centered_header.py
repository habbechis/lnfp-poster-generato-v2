"""Center the fixtures header while preserving the results header."""
from __future__ import annotations

import inspect
import os
import threading

from . import poster

_ORIGINAL_RENDER = poster.render_poster
_ORIGINAL_LOGO = poster._paste_brand_logo
_ORIGINAL_TITLE = poster._paste_title_image
_LOCK = threading.RLock()


def _fixtures_logo(base, cx, cy, box_w, box_h, spec=None):
    # Fixtures-only adjustment: bring the Ligue 1 logo closer to the title
    # and center the complete visible header group. Results are not affected.
    if cx == 1560 and box_w in (420, 430) and cy in (280, 290):
        cx = 1400
    return _ORIGINAL_LOGO(base, cx, cy, box_w, box_h, spec=spec)


def _fixtures_title(base, name, right_x, cy, max_w, max_h):
    # Fixtures-only adjustment: move the title toward the logo without
    # modifying the results title position or renderer.
    if right_x == 1330 and cy in (290, 300):
        right_x = 1150
    return _ORIGINAL_TITLE(base, name, right_x, cy, max_w, max_h)


def _is_fixtures(args, kwargs):
    try:
        bound = inspect.signature(_ORIGINAL_RENDER).bind_partial(*args, **kwargs)
        title_image = bound.arguments.get("title_image")
    except Exception:
        title_image = kwargs.get("title_image")
    return os.path.basename(str(title_image or "")).lower() == "title-fixtures.png"


def _render(*args, **kwargs):
    if not _is_fixtures(args, kwargs):
        return _ORIGINAL_RENDER(*args, **kwargs)
    with _LOCK:
        old_logo = poster._paste_brand_logo
        old_title = poster._paste_title_image
        poster._paste_brand_logo = _fixtures_logo
        poster._paste_title_image = _fixtures_title
        try:
            return _ORIGINAL_RENDER(*args, **kwargs)
        finally:
            poster._paste_brand_logo = old_logo
            poster._paste_title_image = old_title


poster.render_poster = _render
