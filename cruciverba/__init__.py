"""Application factory: configure Flask, then register its components."""

import logging
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix

from cruciverba import admin, contributions
from cruciverba.config import (
    get_app_settings,
    get_celebrated_person_name,
    get_database_path,
    get_trusted_proxy_count,
    validate_production_config,
)
from cruciverba.security import default_rate_limit, register_security_handlers

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def create_app(config=None):
    """Create an independent app; optional settings support tests and embedding."""
    load_dotenv()
    validate_production_config()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    app = Flask(
        __name__,
        template_folder=str(PROJECT_ROOT / "templates"),
        static_folder=str(PROJECT_ROOT / "static"),
    )
    app.config.update(get_app_settings(), DATABASE_PATH=get_database_path())
    app.config.update(config or {})

    proxy_count = get_trusted_proxy_count()
    if proxy_count:
        app.wsgi_app = ProxyFix(
            app.wsgi_app,
            x_for=proxy_count,
            x_proto=proxy_count,
            x_host=proxy_count,
            x_port=proxy_count,
        )

    CSRFProtect(app)
    limiter = Limiter(
        key_func=get_remote_address,
        app=app,
        default_limits=[default_rate_limit],
        storage_uri="memory://",
    )
    # Keep each app's limiter available without sharing mutable global state.
    app.extensions["rate_limiter"] = limiter
    register_security_handlers(app)
    contributions.register_routes(app, limiter)
    admin.register_routes(app, limiter)

    @app.context_processor
    def inject_person_name():
        return {"person_name": get_celebrated_person_name()}

    return app
