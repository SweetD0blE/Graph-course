import re

from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, BooleanField
from wtforms.validators import DataRequired, Email, Regexp


STAFF_NUMBER_RE = r'^\d{8}$'


def _strip_spaces(value):
    """Убирает все пробельные символы (применяется до валидации)."""
    return re.sub(r'\s+', '', value) if isinstance(value, str) else value


class RegisterForm(FlaskForm):
    """Регистрация: ФИО, табельный номер, отдел, должность, почта."""

    full_name = StringField('ФИО', validators=[DataRequired()])
    staff_number = StringField(
        'Табельный номер',
        filters=[_strip_spaces],
        validators=[
            DataRequired(),
            Regexp(STAFF_NUMBER_RE, message='Табельный номер — 8 цифр'),
        ],
    )
    department = StringField('Подразделение', validators=[DataRequired()])
    position = StringField('Должность', validators=[DataRequired()])
    email = StringField(
        'Корпоративная почта', validators=[DataRequired(), Email()]
    )
    policy = BooleanField(validators=[DataRequired()])
    submit = SubmitField('Зарегистрироваться')


class LoginForm(FlaskForm):
    """Вход по табельному номеру и коду подтверждения из письма."""

    staff_number = StringField(
        'Табельный номер',
        filters=[_strip_spaces],
        validators=[
            DataRequired(),
            Regexp(STAFF_NUMBER_RE, message='Табельный номер — 8 цифр'),
        ],
    )
    password = StringField('Код подтверждения', validators=[DataRequired()])
    submit = SubmitField('Войти')


class PasswordRecovery(FlaskForm):
    """Повторная отправка кода подтверждения на почту."""

    staff_number = StringField(
        'Табельный номер',
        filters=[_strip_spaces],
        validators=[
            DataRequired(),
            Regexp(STAFF_NUMBER_RE, message='Табельный номер — 8 цифр'),
        ],
    )
    submit = SubmitField('Выслать код повторно')
