import csv
import io
import logging
import os
import re
import secrets
from contextlib import closing
from datetime import timedelta

from dotenv import load_dotenv
from flask import (
    Flask,
    Response,
    abort,
    flash,
    make_response,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf import CSRFProtect
from flask_wtf.csrf import CSRFError
from werkzeug.exceptions import SecurityError
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash

from cruciverba.config import (
    get_admin_password,
    get_admin_password_hash,
    get_celebrated_person_name,
    get_database_path,
    get_form_password,
    get_form_password_hash,
    get_rate_limit_storage_url,
    get_secret_key,
    get_trusted_hosts,
    get_trusted_proxy_count,
    is_https_forced,
    is_production,
    validate_production_config,
)
from cruciverba.database import connect_to_database, initialize_database
from cruciverba.forms import AdminLoginForm, ContributionForm, LoginForm
from cruciverba.validation import is_valid_clue, is_valid_word, sanitize_csv_cell, sanitize_input


load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
https_enabled = is_https_forced()
csrf_enabled = is_production() or os.getenv("WTF_CSRF_ENABLED", "True").lower() == "true"
rate_limiting_enabled = (
    is_production() or os.getenv("RATELIMIT_ENABLED", "True").lower() == "true"
)
app.config.update(
    SECRET_KEY=get_secret_key(),
    WTF_CSRF_TIME_LIMIT=3600,
    WTF_CSRF_SSL_STRICT=True,
    WTF_CSRF_ENABLED=csrf_enabled,
    RATELIMIT_ENABLED=rate_limiting_enabled,
    SESSION_COOKIE_NAME="__Host-cruciverba_session" if https_enabled else "cruciverba_session",
    SESSION_COOKIE_SECURE=https_enabled,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_PATH="/",
    SESSION_REFRESH_EACH_REQUEST=False,
    PERMANENT_SESSION_LIFETIME=timedelta(hours=2),
    MAX_CONTENT_LENGTH=16 * 1024,
    MAX_FORM_MEMORY_SIZE=16 * 1024,
    MAX_FORM_PARTS=10,
    TRUSTED_HOSTS=get_trusted_hosts(),
    PREFERRED_URL_SCHEME="https" if https_enabled else "http",
)

trusted_proxy_count = get_trusted_proxy_count()
if trusted_proxy_count:
    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_for=trusted_proxy_count,
        x_proto=trusted_proxy_count,
        x_host=trusted_proxy_count,
        x_port=trusted_proxy_count,
    )

csrf = CSRFProtect(app)
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["300 per day", "60 per hour"],
    storage_uri=get_rate_limit_storage_url(),
)


def log_security_event(event_type, details=""):
    client_ip = get_remote_address()
    suffix = f" - {details}" if details else ""
    logger.warning("SECURITY EVENT: %s from %s%s", event_type, client_ip, suffix)


def _verify_password(candidate, plain_password, password_hash):
    if not isinstance(candidate, str):
        return False
    if password_hash:
        try:
            return check_password_hash(password_hash, candidate)
        except (TypeError, ValueError):
            logger.error("Hash password configurato in modo non valido")
            return False
    return secrets.compare_digest(candidate, plain_password)


def init_db():
    initialize_database(get_database_path())


def get_db_connection():
    return connect_to_database(get_database_path())


@app.after_request
def set_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "0"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "base-uri 'self'; "
        "object-src 'none'; "
        "frame-ancestors 'none'; "
        "form-action 'self'; "
        "style-src 'self'; "
        "font-src 'self'; "
        "script-src 'self'; "
        "img-src 'self' data:; "
        "connect-src 'self'"
    )
    # Flask-WTF's HTTPS CSRF check needs a same-origin Referer on form POSTs.
    # Do not leak it to other origins.
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Permissions-Policy"] = (
        "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
    )
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"

    if request.is_secure and https_enabled:
        response.headers["Strict-Transport-Security"] = "max-age=31536000"

    if request.endpoint == "static":
        response.headers["Cache-Control"] = "public, max-age=3600"
    else:
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
    return response


@app.errorhandler(CSRFError)
def handle_csrf_error(error):
    log_security_event("CSRF_ERROR", error.description)
    return render_template(
        "error.html",
        title="Richiesta scaduta",
        message="Ricarica la pagina e riprova.",
    ), 400


@app.errorhandler(429)
def ratelimit_handler(error):
    log_security_event("RATE_LIMIT_EXCEEDED")
    return render_template(
        "error.html",
        title="Troppi tentativi",
        message="Hai effettuato troppi tentativi. Riprova più tardi.",
    ), 429


@app.errorhandler(403)
def forbidden_handler(error):
    return render_template(
        "error.html",
        title="Accesso negato",
        message="Non hai i permessi per aprire questa pagina.",
    ), 403


@app.errorhandler(400)
def bad_request_handler(error):
    # Host validation can fail before Flask creates a URL adapter. In that case,
    # templates containing url_for() cannot be rendered safely.
    if isinstance(error, SecurityError):
        return Response(
            "<!doctype html><html lang=\"it\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<title>Richiesta non valida</title></head><body>"
            "<main><h1>Richiesta non valida</h1>"
            "<p>La richiesta non può essere elaborata.</p></main></body></html>",
            status=400,
            content_type="text/html; charset=utf-8",
        )
    return render_template(
        "error.html",
        title="Richiesta non valida",
        message="La richiesta non può essere elaborata.",
    ), 400


@app.errorhandler(404)
def not_found_handler(error):
    return render_template(
        "error.html",
        title="Pagina non trovata",
        message="La pagina richiesta non esiste.",
    ), 404


@app.errorhandler(405)
def method_not_allowed_handler(error):
    return render_template(
        "error.html",
        title="Operazione non consentita",
        message="Questo collegamento non può eseguire l'operazione richiesta.",
    ), 405


@app.errorhandler(413)
def request_too_large_handler(error):
    return render_template(
        "error.html",
        title="Richiesta troppo grande",
        message="I dati inviati superano il limite consentito.",
    ), 413


@app.errorhandler(500)
def internal_error_handler(error):
    return render_template(
        "error.html",
        title="Errore interno",
        message="Il servizio non può completare la richiesta.",
    ), 500


@app.context_processor
def inject_person_name():
    return {"person_name": get_celebrated_person_name()}


@app.route("/healthz")
@limiter.exempt
def healthcheck():
    return {"status": "ok"}


@app.route("/", methods=["GET", "POST"])
@limiter.limit("30 per minute")
@limiter.limit(
    "5 per minute",
    methods=["POST"],
    exempt_when=lambda: "access_password" not in request.form,
)
def index():
    if request.method == "POST" and "access_password" in request.form:
        form = LoginForm()
        if form.validate_on_submit():
            if _verify_password(
                form.access_password.data,
                get_form_password(),
                get_form_password_hash(),
            ):
                session.clear()
                session["form_access"] = True
                session.permanent = True
                logger.info("Accesso al form riuscito da %s", get_remote_address())
                return redirect(url_for("index"))
            log_security_event("INVALID_FORM_PASSWORD")
            flash("Password errata. Chiedi la password agli organizzatori!", "error")
        return render_template("form_login.html", form=form)

    if not session.get("form_access"):
        if request.method == "POST":
            return redirect(url_for("index"))
        return render_template("form_login.html", form=LoginForm())

    if request.method == "POST":
        if request.form.get("website", "").strip():
            log_security_event("HONEYPOT_TRIGGERED")
            return redirect(url_for("index"))

        form = ContributionForm()
        if form.validate_on_submit():
            parola = sanitize_input(form.parola.data)
            frase_indizio = sanitize_input(form.frase_indizio.data)
            nome = sanitize_input(form.nome.data)

            if not is_valid_word(parola):
                flash("La parola è obbligatoria", "error")
                return render_template("index.html", form=form)
            if not is_valid_clue(frase_indizio):
                flash("La frase indizio è obbligatoria", "error")
                return render_template("index.html", form=form)

            with closing(get_db_connection()) as connection:
                connection.execute(
                    "INSERT INTO submissions (parola, frase_indizio, nome) VALUES (?, ?, ?)",
                    (parola.lower(), frase_indizio, nome),
                )
                connection.commit()

            session["contributor_name"] = nome
            logger.info("Nuovo contributo ricevuto da %s", get_remote_address())
            flash("Grazie! Il tuo contributo è stato registrato.", "success")
            return render_template("success.html", nome=nome)

        for errors in form.errors.values():
            for error in errors:
                flash(error, "error")
        return render_template("index.html", form=form)

    form = ContributionForm()
    form.nome.data = session.get("contributor_name", "")
    return render_template("index.html", form=form)


@app.route("/nuovo-contributo")
def new_contribution():
    if not session.get("form_access"):
        return redirect(url_for("index"))
    return redirect(url_for("index"))


@app.route("/admin", methods=["GET", "POST"])
@limiter.limit("30 per minute")
@limiter.limit("5 per minute", methods=["POST"])
def admin():
    if request.method == "POST":
        form = AdminLoginForm()
        if form.validate_on_submit():
            if _verify_password(
                form.password.data,
                get_admin_password(),
                get_admin_password_hash(),
            ):
                session.clear()
                session["admin_logged_in"] = True
                session.permanent = True
                logger.info("Accesso admin riuscito da %s", get_remote_address())
                return redirect(url_for("admin"))
            log_security_event("INVALID_ADMIN_PASSWORD")
            flash("Password errata", "error")
        return render_template("admin_login.html", form=form)

    if not session.get("admin_logged_in"):
        return render_template("admin_login.html", form=AdminLoginForm())

    with closing(get_db_connection()) as connection:
        submissions = connection.execute(
            "SELECT * FROM submissions ORDER BY timestamp DESC"
        ).fetchall()
    return render_template("admin.html", submissions=submissions)


@app.route("/admin/export")
@limiter.limit("10 per minute")
def export_csv():
    if not session.get("admin_logged_in"):
        abort(403)

    try:
        with closing(get_db_connection()) as connection:
            submissions = connection.execute(
                "SELECT parola, frase_indizio, nome, timestamp "
                "FROM submissions ORDER BY timestamp DESC"
            ).fetchall()

        output_stream = io.StringIO()
        writer = csv.writer(output_stream)
        writer.writerow(["Parola", "Frase Indizio", "Nome", "Data"])
        for submission in submissions:
            writer.writerow(
                [
                    sanitize_csv_cell(submission["parola"]),
                    sanitize_csv_cell(submission["frase_indizio"]),
                    sanitize_csv_cell(submission["nome"] or "Anonimo"),
                    submission["timestamp"],
                ]
            )

        safe_name = re.sub(
            r"[^a-z0-9_-]+",
            "_",
            get_celebrated_person_name().lower(),
        ).strip("_") or "laurea"
        response = make_response(output_stream.getvalue().encode("utf-8"))
        response.headers["Content-Type"] = "text/csv; charset=utf-8"
        response.headers["Content-Disposition"] = (
            f"attachment; filename=cruciverba_{safe_name}.csv"
        )
        logger.info("CSV esportato da %s", get_remote_address())
        return response
    except Exception:
        logger.exception("Errore durante esportazione CSV")
        flash("Errore durante l'esportazione", "error")
        return redirect(url_for("admin"))


@app.route("/admin/delete/<int:submission_id>", methods=["POST"])
@limiter.limit("30 per minute")
def delete_submission(submission_id):
    if not session.get("admin_logged_in"):
        abort(403)
    if submission_id <= 0:
        abort(400)

    try:
        with closing(get_db_connection()) as connection:
            result = connection.execute(
                "SELECT id FROM submissions WHERE id = ?", (submission_id,)
            ).fetchone()
            if not result:
                flash("Contributo non trovato", "error")
                return redirect(url_for("admin"))
            connection.execute("DELETE FROM submissions WHERE id = ?", (submission_id,))
            connection.commit()

        logger.info("Contributo %s eliminato da %s", submission_id, get_remote_address())
        flash("Contributo eliminato", "success")
    except Exception:
        logger.exception("Errore durante eliminazione contributo")
        flash("Errore durante l'eliminazione", "error")
    return redirect(url_for("admin"))


@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("index"))


@app.route("/logout", methods=["POST"])
def form_logout():
    session.clear()
    flash("Sei stato disconnesso", "success")
    return redirect(url_for("index"))


if __name__ == "__main__":
    if is_production():
        validate_production_config()
        raise RuntimeError("In produzione avvia l'applicazione con Gunicorn tramite wsgi.py")
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=False)
