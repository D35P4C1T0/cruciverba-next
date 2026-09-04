"""Form e messaggi di validazione mostrati agli utenti."""

from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField, TextAreaField
from wtforms.validators import DataRequired, Length


class LoginForm(FlaskForm):
    access_password = PasswordField(
        "Password di accesso",
        validators=[
            DataRequired(message="La password è obbligatoria"),
            Length(max=256, message="La password non è valida"),
        ],
    )


class AdminLoginForm(FlaskForm):
    password = PasswordField(
        "Password",
        validators=[
            DataRequired(message="La password è obbligatoria"),
            Length(max=256, message="La password non è valida"),
        ],
    )


class ContributionForm(FlaskForm):
    parola = StringField(
        "Parola",
        validators=[
            DataRequired(message="La parola è obbligatoria"),
            Length(min=1, max=50, message="La parola deve essere tra 1 e 50 caratteri"),
        ],
    )
    frase_indizio = TextAreaField(
        "Frase indizio",
        validators=[
            DataRequired(message="La frase indizio è obbligatoria"),
            Length(min=1, max=200, message="La frase indizio non può superare 200 caratteri"),
        ],
    )
    nome = StringField(
        "Il tuo nome",
        validators=[
            DataRequired(message="Il nome è obbligatorio"),
            Length(min=1, max=50, message="Il nome deve essere tra 1 e 50 caratteri"),
        ],
    )
