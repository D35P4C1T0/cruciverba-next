"""Organizer login, contribution management and downloads."""

import csv
import io
import logging

from flask import (
    abort,
    flash,
    make_response,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_limiter.util import get_remote_address

from cruciverba.config import (
    get_admin_password,
    get_admin_password_hash,
    get_celebrated_person_name,
)
from cruciverba.database import list_submissions, remove_submission
from cruciverba.forms import AdminLoginForm
from cruciverba.exports import create_pdf_bytes, export_filename
from cruciverba.security import (
    is_failed_login,
    login_rate_limit,
    log_security_event,
    verify_password,
)
from cruciverba.validation import sanitize_csv_cell

logger = logging.getLogger(__name__)


def admin():
    if request.method == "POST":
        return login_admin()

    if not session.get("admin_logged_in"):
        return render_template("admin_login.html", form=AdminLoginForm())

    submissions = list_submissions()
    return render_template("admin.html", submissions=submissions)


def export_csv():
    if not session.get("admin_logged_in"):
        abort(403)

    try:
        submissions = list_submissions()

        response = create_csv_response(submissions)

        logger.info("CSV esportato da %s", get_remote_address())
        return response
    except Exception:
        logger.exception("Errore durante esportazione CSV")
        flash("Errore durante l'esportazione", "error")
        return redirect(url_for("admin"))


def export_pdf():
    if not session.get("admin_logged_in"):
        abort(403)

    try:
        person_name = get_celebrated_person_name()
        content = create_pdf_bytes(list_submissions(), person_name)
        response = make_response(content)
        response.headers["Content-Type"] = "application/pdf"
        response.headers["Content-Disposition"] = (
            f"attachment; filename={export_filename(person_name, 'pdf')}"
        )
        logger.info("PDF esportato da %s", get_remote_address())
        return response
    except Exception:
        logger.exception("Errore durante esportazione PDF")
        flash("Errore durante l'esportazione", "error")
        return redirect(url_for("admin"))


def delete_submission(submission_id):
    if not session.get("admin_logged_in"):
        abort(403)
    if submission_id <= 0:
        abort(400)

    try:
        if not remove_submission(submission_id):
            flash("Contributo non trovato", "error")
            return redirect(url_for("admin"))

        logger.info("Contributo %s eliminato da %s", submission_id, get_remote_address())
        flash("Contributo eliminato", "success")
    except Exception:
        logger.exception("Errore durante eliminazione contributo")
        flash("Errore durante l'eliminazione", "error")
    return redirect(url_for("admin"))


def admin_logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("index"))


def login_admin():
    form = AdminLoginForm()
    if form.validate_on_submit():
        if verify_password(
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


def create_csv_response(submissions):
    """Export sanitized cells and a safe, event-specific filename."""
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

    response = make_response(output_stream.getvalue().encode("utf-8"))
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = (
        f"attachment; filename={export_filename(get_celebrated_person_name(), 'csv')}"
    )
    return response


def register_routes(app, limiter):
    admin_login = limiter.limit(
        login_rate_limit,
        methods=["POST"],
        deduct_when=is_failed_login,
        override_defaults=False,
    )(admin)
    app.add_url_rule("/admin", view_func=admin_login, methods=["GET", "POST"])
    app.add_url_rule("/admin/export", view_func=export_csv)
    app.add_url_rule("/admin/export/pdf", view_func=export_pdf)
    app.add_url_rule(
        "/admin/delete/<int:submission_id>", view_func=delete_submission, methods=["POST"],
    )
    app.add_url_rule("/admin/logout", view_func=admin_logout, methods=["POST"])
