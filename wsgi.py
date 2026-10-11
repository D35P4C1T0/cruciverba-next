"""Production WSGI entrypoint used by Gunicorn."""

from app import app
from cruciverba.database import init_db

with app.app_context():
    init_db()

application = app
