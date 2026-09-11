"""Service layer: teams registry, persistence store and poster renderer."""

# Apply the poster header alignment patch before the app imports the renderer.
from . import centered_header  # noqa: F401,E402
