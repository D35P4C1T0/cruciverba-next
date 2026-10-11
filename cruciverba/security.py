"""Password verification, rate-limit rules and HTTP security policies."""

import logging
import os
import secrets

from flask import Response, current_app, render_template, request
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFError
from werkzeug.exceptions import SecurityError
from werkzeug.security import check_password_hash

logger = logging.getLogger(__name__)


def log_security_event(event_type, details=""):
    client_ip = get_remote_address()
    suffix = f" - {details}" if details else ""
    logger.warning("SECURITY EVENT: %s from %s%s", event_type, client_ip, suffix)


def verify_password(candidate, plain_password, password_hash):
    if not isinstance(candidate, str):
        return False
    if password_hash:
        try:
            return check_password_hash(password_hash, candidate)
        except (TypeError, ValueError):
            logger.error("Hash password configurato in modo non valido")
            return False
    return secrets.compare_digest(candidate, plain_password)


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

    if request.is_secure and current_app.config["SESSION_COOKIE_SECURE"]:
        response.headers["Strict-Transport-Security"] = "max-age=31536000"

    if request.endpoint == "static":
        response.headers["Cache-Control"] = "public, max-age=3600"
    else:
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
    return response


def handle_csrf_error(error):
    log_security_event("CSRF_ERROR", error.description)
    return render_template(
        "error.html",
        title="Richiesta scaduta",
        message="Ricarica la pagina e riprova.",
    ), 400


def ratelimit_handler(error):
    log_security_event("RATE_LIMIT_EXCEEDED")
    return render_template(
        "error.html",
        title="Troppi tentativi",
        message="Hai effettuato troppi tentativi. Riprova più tardi.",
    ), 429


def forbidden_handler(error):
    return render_template(
        "error.html",
        title="Accesso negato",
        message="Non hai i permessi per aprire questa pagina.",
    ), 403


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


def not_found_handler(error):
    return render_template(
        "error.html",
        title="Pagina non trovata",
        message="La pagina richiesta non esiste.",
    ), 404


def method_not_allowed_handler(error):
    return render_template(
        "error.html",
        title="Operazione non consentita",
        message="Questo collegamento non può eseguire l'operazione richiesta.",
    ), 405


def request_too_large_handler(error):
    return render_template(
        "error.html",
        title="Richiesta troppo grande",
        message="I dati inviati superano il limite consentito.",
    ), 413


def internal_error_handler(error):
    return render_template(
        "error.html",
        title="Errore interno",
        message="Il servizio non può completare la richiesta.",
    ), 500


def default_rate_limit():
    return os.getenv("RATE_LIMIT_DEFAULT", "120 per minute")


def login_rate_limit():
    return os.getenv("RATE_LIMIT_LOGIN", "10 per minute")


def is_failed_login(response):
    # Login errors render the form; successful logins redirect.
    return response.status_code == 200


def is_contribution_request():
    return "access_password" not in request.form


def register_security_handlers(app):
    app.after_request(set_security_headers)
    for error, handler in {
        CSRFError: handle_csrf_error,
        400: bad_request_handler,
        403: forbidden_handler,
        404: not_found_handler,
        405: method_not_allowed_handler,
        413: request_too_large_handler,
        429: ratelimit_handler,
        500: internal_error_handler,
    }.items():
        app.register_error_handler(error, handler)
