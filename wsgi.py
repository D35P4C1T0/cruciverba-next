"""Entrypoint WSGI usato da Gunicorn."""

from app import app, init_db
from cruciverba.config import validate_production_config


validate_production_config()
init_db()
application = app
