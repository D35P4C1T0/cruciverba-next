"""Configurazione applicativa e controlli fail-closed per la produzione."""

import logging
import os
import secrets
from datetime import timedelta
from pathlib import Path


DEFAULT_PERSON_NAME = "Bianca"
DEFAULT_FORM_PASSWORD = "bianca"
DEFAULT_ADMIN_PASSWORD = "bianca2024"
PLACEHOLDER_PARTS = ("cambia-questa", "incolla-qui", "change-me")
logger = logging.getLogger(__name__)


def _read_secret(name, default=None):
    """Read NAME_FILE first, then NAME. Docker secrets stay out of inspect output."""
    secret_file = os.getenv(f"{name}_FILE")
    if secret_file:
        try:
            return Path(secret_file).read_text(encoding="utf-8").strip()
        except OSError as error:
            raise RuntimeError(f"Impossibile leggere {name}_FILE") from error
    return os.getenv(name, default)


def get_environment():
    return os.getenv("APP_ENV", os.getenv("FLASK_ENV", "development")).lower()


def is_production():
    return get_environment() == "production"


def get_secret_key():
    configured_key = _read_secret("SECRET_KEY")
    if configured_key:
        return configured_key
    return secrets.token_hex(32)


def get_form_password():
    return _read_secret("FORM_PASSWORD", DEFAULT_FORM_PASSWORD)


def get_admin_password():
    return _read_secret("ADMIN_PASSWORD", DEFAULT_ADMIN_PASSWORD)


def get_form_password_hash():
    return _read_secret("FORM_PASSWORD_HASH")


def get_admin_password_hash():
    return _read_secret("ADMIN_PASSWORD_HASH")


def get_celebrated_person_name():
    name = os.getenv("CELEBRATED_PERSON_NAME", DEFAULT_PERSON_NAME).strip()
    return name or DEFAULT_PERSON_NAME


def get_database_path():
    return os.getenv("DATABASE_PATH", "data/cruciverba.db")


def get_trusted_hosts():
    value = os.getenv("TRUSTED_HOSTS", "")
    return [host.strip() for host in value.split(",") if host.strip()] or None


def get_trusted_proxy_count():
    raw_value = os.getenv("TRUSTED_PROXY_COUNT", "0")
    try:
        count = int(raw_value)
    except ValueError as error:
        raise RuntimeError("TRUSTED_PROXY_COUNT deve essere un numero intero") from error
    if not 0 <= count <= 5:
        raise RuntimeError("TRUSTED_PROXY_COUNT deve essere tra 0 e 5")
    return count


def is_https_forced():
    return os.getenv("FORCE_HTTPS", "False").lower() == "true"


def are_weak_passwords_allowed():
    return os.getenv("ALLOW_WEAK_PASSWORDS", "False").strip().lower() == "true"


def _is_weak(value, default):
    normalized = (value or "").lower()
    return (
        len(value or "") < 12
        or value == default
        or any(part in normalized for part in PLACEHOLDER_PARTS)
    )


def _is_supported_password_hash(value):
    return bool(value) and value.startswith(("scrypt:", "pbkdf2:")) and value.count("$") == 2


def validate_production_config():
    """Refuse unsafe production startup instead of using development defaults."""
    if not is_production():
        return

    errors = []
    secret_key = _read_secret("SECRET_KEY")
    if not secret_key or len(secret_key) < 32 or any(
        part in secret_key.lower() for part in PLACEHOLDER_PARTS
    ):
        errors.append("SECRET_KEY deve essere casuale e lunga almeno 32 caratteri")

    form_hash = get_form_password_hash()
    admin_hash = get_admin_password_hash()
    if form_hash and not _is_supported_password_hash(form_hash):
        errors.append("FORM_PASSWORD_HASH non è un hash Werkzeug supportato")
    if admin_hash and not _is_supported_password_hash(admin_hash):
        errors.append("ADMIN_PASSWORD_HASH non è un hash Werkzeug supportato")
    if are_weak_passwords_allowed():
        logger.warning(
            "ALLOW_WEAK_PASSWORDS=True: controllo robustezza password disattivato"
        )
    else:
        if not form_hash and _is_weak(get_form_password(), DEFAULT_FORM_PASSWORD):
            errors.append(
                "FORM_PASSWORD deve avere almeno 12 caratteri, oppure usa "
                "FORM_PASSWORD_HASH o ALLOW_WEAK_PASSWORDS=True"
            )
        if not admin_hash and _is_weak(get_admin_password(), DEFAULT_ADMIN_PASSWORD):
            errors.append(
                "ADMIN_PASSWORD deve avere almeno 12 caratteri, oppure usa "
                "ADMIN_PASSWORD_HASH o ALLOW_WEAK_PASSWORDS=True"
            )
    if not is_https_forced():
        errors.append("FORCE_HTTPS deve essere True in produzione")
    if not get_trusted_hosts():
        errors.append("TRUSTED_HOSTS deve contenere il dominio pubblico")

    if errors:
        raise RuntimeError("Configurazione di produzione non sicura: " + "; ".join(errors))


def get_app_settings():
    """Build Flask settings from the environment in one place."""
    https_enabled = is_https_forced()
    csrf_enabled = is_production() or os.getenv("WTF_CSRF_ENABLED", "True").lower() == "true"
    rate_limiting_enabled = (
        is_production() or os.getenv("RATELIMIT_ENABLED", "True").lower() == "true"
    )
    return dict(
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
