from functools import wraps

from flask import (
    Blueprint, render_template, abort, request, redirect, url_for, flash,
)
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Topic, Question, AnswerOption, Users
from app.app_logger import logger

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if current_user.status != 1:
            abort(403)
        return view(*args, **kwargs)
    return wrapped


@admin_bp.route('/claim')
@login_required
def claim():
    """Бутстрап первого администратора: работает, пока админов нет."""
    if Users.query.filter_by(status=1).count() > 0:
        abort(403)
    current_user.status = 1
    db.session.commit()
    logger.info(
        f'Пользователь {current_user.staff_number} назначен '
        f'администратором (bootstrap)'
    )
    flash('Вы назначены администратором.', 'success')
    return redirect(url_for('admin.tests'))


@admin_bp.route('/tests')
@admin_required
def tests():
    topics = (
        Topic.query
        .join(Question)
        .order_by(Topic.order)
        .distinct()
        .all()
    )
    rows = []
    for t in topics:
        total = len(t.questions)
        configured = sum(
            1 for q in t.questions if any(o.is_correct for o in q.options)
        )
        rows.append({'topic': t, 'total': total, 'configured': configured})
    return render_template('admin_tests.html', rows=rows)


@admin_bp.route('/topic/<int:topic_id>/answers', methods=['GET', 'POST'])
@admin_required
def answers(topic_id):
    topic = Topic.query.get_or_404(topic_id)
    if not topic.questions:
        flash('У этой темы нет вопросов.', 'info')
        return redirect(url_for('admin.tests'))

    if request.method == 'POST':
        selected = set(request.form.getlist('correct'))
        for q in topic.questions:
            for o in q.options:
                o.is_correct = str(o.id) in selected
        db.session.commit()
        logger.info(
            f'Правильные ответы темы {topic.code} обновлены '
            f'администратором {current_user.staff_number}'
        )
        flash('Правильные ответы сохранены.', 'success')
        return redirect(url_for('admin.tests'))

    return render_template('admin_answers.html', topic=topic)
