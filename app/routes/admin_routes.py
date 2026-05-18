from functools import wraps

from flask import (
    Blueprint, render_template, abort, request, redirect, url_for, flash,
)
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Topic, Question, AnswerOption, Users, TestAttempt
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


def _test_topics():
    """Темы, где задан хотя бы один правильный ответ (есть зачётный тест)."""
    topics = Topic.query.order_by(Topic.order).all()
    return [
        t for t in topics
        if any(any(o.is_correct for o in q.options) for q in t.questions)
    ]


@admin_bp.route('/users')
@admin_required
def users():
    test_topics = _test_topics()
    test_topic_ids = {t.id for t in test_topics}
    total = len(test_topics)

    by_user = {}
    for a in TestAttempt.query.all():
        d = by_user.setdefault(
            a.user_id, {'passed': set(), 'count': 0, 'last': None}
        )
        d['count'] += 1
        if a.passed and a.topic_id in test_topic_ids:
            d['passed'].add(a.topic_id)
        if d['last'] is None or (a.created_at and a.created_at > d['last']):
            d['last'] = a.created_at

    rows = []
    for u in Users.query.order_by(Users.full_name).all():
        d = by_user.get(u.id, {'passed': set(), 'count': 0, 'last': None})
        passed = len(d['passed'])
        rows.append({
            'user': u,
            'passed': passed,
            'total': total,
            'progress': round(passed / total * 100) if total else 0,
            'attempts': d['count'],
            'last_at': d['last'],
        })
    return render_template('admin_users.html', rows=rows)


@admin_bp.route('/users/<int:user_id>')
@admin_required
def user_card(user_id):
    user = Users.query.get_or_404(user_id)
    test_topics = _test_topics()

    by_topic = {}
    attempts = (
        TestAttempt.query
        .filter_by(user_id=user.id)
        .all()
    )
    for a in attempts:
        d = by_topic.setdefault(
            a.topic_id,
            {'best': 0, 'passed': False, 'count': 0, 'last': None},
        )
        d['count'] += 1
        d['best'] = max(d['best'], a.score)
        d['passed'] = d['passed'] or a.passed
        if d['last'] is None or (a.created_at and a.created_at > d['last']):
            d['last'] = a.created_at

    topic_rows = []
    for t in test_topics:
        d = by_topic.get(
            t.id, {'best': 0, 'passed': False, 'count': 0, 'last': None}
        )
        topic_rows.append({
            'topic': t,
            'best': d['best'],
            'passed': d['passed'],
            'attempts': d['count'],
            'last_at': d['last'],
        })
    return render_template(
        'admin_user.html', user=user, topic_rows=topic_rows
    )
