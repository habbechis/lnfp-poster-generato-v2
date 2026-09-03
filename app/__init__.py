"""Application factory for the LNFP match-day poster generator."""
from __future__ import annotations

from flask import Flask

from config import Config
from .services.store import Store


def create_app(config_object: type = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object)
    # Keep the config class itself for services that want attribute access
    # (typed defaults, ints) rather than Flask's dict-style app.config.
    app.config_object = config_object

    # Single shared persistence store for the process. Pass the config object
    # itself (attribute access) rather than Flask's dict-style app.config.
    app.store = Store(config_object)

    # Administrator accounts (super admin manages the rest).
    from .services.admins import AdminService
    app.admins = AdminService(app.store, config_object)

    from .routes.views import bp as views_bp
    from .routes.api import bp as api_bp
    from .routes.admin import bp as admin_bp
    app.register_blueprint(views_bp)
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(admin_bp)

    # The KICK OFF data/API stays unchanged; only its server-side visual
    # renderer is swapped for the reference-driven implementation.
    from .services import kickoff_reference, poster
    poster.render_kickoff = kickoff_reference.render_kickoff

    @app.get("/healthz")
    def healthz():
        return {"status": "ok", "store": app.store.status()}

    return app
