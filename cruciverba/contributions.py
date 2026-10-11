"""Guest access and contribution pages."""

import logging

from flask import flash, redirect, render_template, request, session, url_for
from flask_limiter.util import get_remote_address

from cruciverba.config import get_form_password, get_form_password_hash
from cruciverba.database import add_submission
from cruciverba.forms import ContributionForm, LoginForm
from cruciverba.security import (
    is_contribution_request,
    is_failed_login,
    login_rate_limit,
    log_security_event,
    verify_password,
)
from cruciverba.validation import is_valid_clue, is_valid_word, sanitize_input

logger = logging.getLogger(__name__)


def healthcheck():
    return {"status": "ok"}


def index():
    if request.method == "POST" and "access_password" in request.form:
        return login_guest()

    if not session.get("form_access"):
        if request.method == "POST":
            return redirect(url_for("index"))
        return render_template("form_login.html", form=LoginForm())

    if request.method == "POST":
        return submit_contribution()

    form = ContributionForm()
    form.nome.data = session.get("contributor_name", "")
    return render_template("index.html", form=form)


def new_contribution():
    return redirect(url_for("index"))


def login_guest():
    form = LoginForm()
    if form.validate_on_submit():
        if verify_password(
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


def submit_contribution():
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

        add_submission(parola.lower(), frase_indizio, nome)

        session["contributor_name"] = nome
        logger.info("Nuovo contributo ricevuto da %s", get_remote_address())
        flash("Grazie! Il tuo contributo è stato registrato.", "success")
        return render_template("success.html", nome=nome)

    for errors in form.errors.values():
        for error in errors:
            flash(error, "error")
    return render_template("index.html", form=form)


def form_logout():
    session.clear()
    flash("Sei stato disconnesso", "success")
    return redirect(url_for("index"))


def register_routes(app, limiter):
    app.add_url_rule("/healthz", view_func=limiter.exempt(healthcheck))
    guest_login = limiter.limit(
        login_rate_limit,
        methods=["POST"],
        exempt_when=is_contribution_request,
        deduct_when=is_failed_login,
        override_defaults=False,
    )(index)
    app.add_url_rule("/", view_func=guest_login, methods=["GET", "POST"])
    app.add_url_rule("/nuovo-contributo", view_func=new_contribution)
    app.add_url_rule("/logout", view_func=form_logout, methods=["POST"])
