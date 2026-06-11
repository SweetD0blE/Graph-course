import random
import string

from flask import (
    Blueprint, render_template, redirect, url_for, session, flash, request,
    jsonify
)
from flask_login import (
    login_user, logout_user, current_user, login_required
)

from app.extensions import db
from app.forms import LoginForm, RegisterForm, PasswordRecovery
from app.models import Users, Employee, Section, Topic, TestAttempt
from app.progress import passed_topic_ids, section_progress
from app.utils import send_internal_mail
from app.app_logger import logger

auth_bp = Blueprint('auth', __name__)


def generate_code(length: int = 6) -> str:
    """Случайный числовой код длиной length."""
    return ''.join(random.choices(string.digits, k=length))


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    recovery_form = PasswordRecovery()

    if current_user.is_authenticated:
        flash('Вы уже авторизованы.', 'info')
        return redirect(url_for('main.index'))

    # Вход по табельному номеру + коду
    if form.submit.data and form.validate_on_submit():
        staff_number = form.staff_number.data
        code = form.password.data

        user = Users.query.filter_by(
            staff_number=staff_number, verification_code=code
        ).first()

        if user:
            login_user(user)
            user.is_verified = True
            db.session.commit()
            logger.info(f'Пользователь {user.staff_number} вошёл в систему')
            flash('Вы успешно вошли.', 'success')
            return redirect(url_for('main.index'))

        logger.warning(f'Неудачный вход по табельному {staff_number}')
        flash('Ошибка авторизации, проверьте табельный номер и код.', 'danger')
        return redirect(url_for('auth.login'))

    # Повторная отправка кода
    if recovery_form.submit.data and recovery_form.validate_on_submit():
        user = Users.query.filter_by(
            staff_number=recovery_form.staff_number.data
        ).first()

        if not user:
            flash(
                'Аккаунт не найден. Проверьте табельный номер или '
                'зарегистрируйтесь.',
                'warning',
            )
            return redirect(url_for('auth.login'))

        send_internal_mail(
            user.email,
            f'Ваш табельный номер: {user.staff_number}\n'
            f'Ваш код подтверждения: {user.verification_code}',
        )
        logger.info(
            f'Повторно выслан код пользователю {user.staff_number} '
            f'на {user.email}'
        )
        flash('Код подтверждения повторно выслан на почту.', 'info')
        return redirect(url_for('auth.login'))

    return render_template(
        'login.html',
        form=form,
        recovery=recovery_form,
        sections_total=Section.query.count(),
        topics_total=Topic.query.count(),
        practices_total=Topic.query.filter(
            Topic.notebook_filename.isnot(None)
        ).count(),
    )


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        flash('Вы уже авторизованы.', 'info')
        return redirect(url_for('main.index'))

    form = RegisterForm()

    if form.validate_on_submit():
        full_name = form.full_name.data
        staff_number = form.staff_number.data
        department = form.department.data
        position = form.position.data
        email = form.email.data

        existing_user = Users.query.filter(
            (Users.email == email) | (Users.staff_number == staff_number)
        ).first()

        if existing_user:
            flash(
                'У вас уже есть аккаунт. Если забыли код — восстановите его '
                'на странице входа.',
                'danger',
            )
            return redirect(url_for('auth.login'))

        code = generate_code()
        user = Users(
            full_name=full_name,
            staff_number=staff_number,
            department=department,
            position=position,
            email=email,
            verification_code=code,
            is_verified=False,
        )
        db.session.add(user)
        db.session.commit()
        logger.info(
            f'Зарегистрирован новый пользователь: {staff_number} ({email})'
        )

        send_internal_mail(
            email,
            f'Ваш табельный номер: {staff_number}\n'
            f'Ваш код подтверждения: {code}',
        )

        flash(
            'Регистрация успешна! Код подтверждения отправлен на '
            'корпоративную почту.',
            'success',
        )
        return redirect(url_for('auth.login'))

    return render_template('register.html', form=form)


@auth_bp.route('/register/employees')
def register_employees():
    """Подсказки сотрудников для автозаполнения формы регистрации.

    Источник — справочник Employee (импорт из SVA_persons.xlsx).
    Мин. длина запроса 2 и лимит 10 — против массового скрейпинга.
    """
    q = (request.args.get('q') or '').strip()
    if len(q) < 2:
        return jsonify([])

    rows = (
        Employee.query
        .filter(Employee.full_name.ilike(f'%{q}%'))
        .order_by(Employee.full_name)
        .limit(10)
        .all()
    )
    return jsonify([
        {
            'full_name': e.full_name or '',
            'staff_number': e.staff_number or '',
            'email': e.email or '',
            'department': e.department or '',
            'position': e.position or '',
        }
        for e in rows
    ])


@auth_bp.route('/profile')
@login_required
def profile():
    user_status = (
        'Администратор' if current_user.status == 1 else 'Слушатель'
    )
    sections = Section.query.order_by(Section.order).all()
    passed_ids = passed_topic_ids(current_user)
    progress = {s.id: section_progress(s, passed_ids) for s in sections}
    tt = sum(p['total_test'] for p in progress.values())
    pp = sum(p['passed'] for p in progress.values())
    overall = round(pp / tt * 100) if tt else 0
    attempts_total = TestAttempt.query.filter(
        TestAttempt.user_id == current_user.id,
        TestAttempt.block != 0,        # «Идти дальше» — не попытка
        TestAttempt.passed.is_(False),  # попытка = неудачная отправка
    ).count()
    return render_template(
        'profile.html',
        user_status=user_status,
        sections=sections,
        progress=progress,
        overall=overall,
        passed_total=pp,
        attempts_total=attempts_total,
    )


@auth_bp.route('/logout')
@login_required
def logout():
    staff_number = current_user.staff_number
    current_user.is_verified = False
    db.session.commit()
    logout_user()
    session.clear()
    logger.info(f'Пользователь {staff_number} вышел из системы')
    flash('Вы вышли из системы.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.before_request
def check_user_verified():
    """Сбрасывает сессию неподтверждённого пользователя."""
    if request.endpoint == 'static':
        return
    if request.method == 'POST':
        return
    if current_user.is_authenticated and not current_user.is_verified:
        logout_user()
        session.clear()
        flash('Ваша сессия была сброшена.', 'warning')
        return redirect(url_for('auth.login'))
