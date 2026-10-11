"""Local entrypoint. Production uses wsgi.py through Gunicorn."""

from cruciverba import create_app
from cruciverba.config import is_production
from cruciverba.database import init_db

app = create_app()


if __name__ == "__main__":
    if is_production():
        raise RuntimeError("In produzione avvia l'applicazione con Gunicorn tramite wsgi.py")
    with app.app_context():
        init_db()
    app.run(host="0.0.0.0", port=5000, debug=False)
