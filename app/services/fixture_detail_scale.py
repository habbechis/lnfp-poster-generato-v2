"""Readable match-card details without changing match data or team results.

This patch is intentionally limited to the standard fixtures poster renderer:
- enlarge the broadcaster/stadium area slightly while keeping it inside the bar;
- slightly increase stadium-label fitting size;
- leave scores, teams, logos, dates and all match payloads untouched.
"""
from . import poster


_original_draw_channels = poster._draw_channels
_original_fit_font = poster._fit_font


def _readable_draw_channels(base, logos, cx, cy, box_h, max_total_w,
                            tv_x=None, combined=None):
    # The original channel mark is too small on mobile previews. Increase it
    # modestly and lift it so the enlarged mark remains inside the match bar.
    enlarged_h = box_h * 1.25
    lifted_cy = cy - box_h * 0.23
    return _original_draw_channels(
        base, logos, cx, lifted_cy, enlarged_h, max_total_w,
        tv_x=tv_x, combined=combined,
    )


def _readable_fit_font(draw, text, max_w, start_size, weight="Bold",
                       min_size=22, rtl=True, role="text", font_path=None):
    # Fixture stadium labels are the only small, narrow labels in this range.
    # Increase their starting size, while retaining the existing width fitting
    # safeguard so text cannot exceed its allocated space.
    if 200 <= max_w <= 360 and 18 <= start_size <= 36:
        start_size = int(round(start_size * 1.16))
    return _original_fit_font(
        draw, text, max_w, start_size, weight, min_size,
        rtl, role, font_path,
    )


poster._draw_channels = _readable_draw_channels
poster._fit_font = _readable_fit_font
