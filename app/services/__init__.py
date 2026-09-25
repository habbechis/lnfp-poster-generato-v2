"""Service layer: teams registry, persistence store and poster renderer."""

# Apply poster alignment/readability patches before the app imports the renderer.
from . import centered_header  # noqa: F401,E402
from . import fixture_detail_scale  # noqa: F401,E402
