import os
from functools import wraps

from flask import (
    Blueprint, render_template, abort, request, redirect, url_for, flash,
)
from flask_login import login_required, current_user

from app.extensions import db
from app.config import Settings
from app.models import (
    Topic, Question, AnswerOption, Users, TestAttempt, NotebookTask,
    NotebookAttempt,
)
from app.progress import topic_passed, topic_test_blocks, is_gradable
from app.utils import parse_notebook
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
    """Темы, гейтящие прогресс (мини-тесты блоков или ноутбук)."""
    return [
        t for t in Topic.query.order_by(Topic.order).all()
        if is_gradable(t)
    ]


@admin_bp.route('/users')
@admin_required
def users():
    test_topics = _test_topics()
    total = len(test_topics)

    by_user = {}
    for a in TestAttempt.query.all():
        d = by_user.setdefault(
            a.user_id, {'passed': set(), 'count': 0, 'last': None}
        )
        d['count'] += 1
        if a.passed:
            d['passed'].add((a.topic_id, a.block))
        if d['last'] is None or (a.created_at and a.created_at > d['last']):
            d['last'] = a.created_at

    rows = []
    for u in Users.query.order_by(Users.full_name).all():
        d = by_user.get(u.id, {'passed': set(), 'count': 0, 'last': None})
        passed = sum(
            1 for t in test_topics if topic_passed(t, u, d['passed'])
        )
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

    attempts = TestAttempt.query.filter_by(user_id=user.id).all()
    passed_set = {(a.topic_id, a.block) for a in attempts if a.passed}

    by_topic = {}
    for a in attempts:
        d = by_topic.setdefault(
            a.topic_id, {'best': 0, 'count': 0, 'last': None}
        )
        d['count'] += 1
        d['best'] = max(d['best'], a.score)
        if d['last'] is None or (a.created_at and a.created_at > d['last']):
            d['last'] = a.created_at

    topic_rows = []
    for t in test_topics:
        d = by_topic.get(t.id, {'best': 0, 'count': 0, 'last': None})
        tb = topic_test_blocks(t)
        blocks_passed = sum(1 for b in tb if (t.id, b) in passed_set)
        topic_rows.append({
            'topic': t,
            'best': d['best'],
            'passed': topic_passed(t, user, passed_set),
            'blocks_passed': blocks_passed,
            'blocks_total': len(tb),
            'attempts': d['count'],
            'last_at': d['last'],
        })
    return render_template(
        'admin_user.html', user=user, topic_rows=topic_rows
    )


@admin_bp.route(
    '/users/<int:user_id>/reset/<int:topic_id>', methods=['POST']
)
@admin_required
def reset_attempts(user_id, topic_id):
    user = Users.query.get_or_404(user_id)
    Topic.query.get_or_404(topic_id)
    TestAttempt.query.filter_by(
        user_id=user.id, topic_id=topic_id
    ).delete()
    NotebookAttempt.query.filter_by(
        user_id=user.id, topic_id=topic_id
    ).delete()
    db.session.commit()
    logger.info(
        f'Прохождение темы {topic_id} пользователя {user.staff_number} '
        f'сброшено администратором {current_user.staff_number}'
    )
    flash('Прохождение темы сброшено.', 'success')
    return redirect(url_for('admin.user_card', user_id=user.id))


@admin_bp.route('/users/<int:user_id>/role', methods=['POST'])
@admin_required
def set_role(user_id):
    user = Users.query.get_or_404(user_id)
    if user.status == 1:
        if Users.query.filter_by(status=1).count() <= 1:
            flash('Нельзя снять последнего администратора.', 'danger')
            return redirect(request.referrer or url_for('admin.users'))
        user.status = 0
        msg = 'снят с роли администратора'
    else:
        user.status = 1
        msg = 'назначен администратором'
    db.session.commit()
    logger.info(
        f'Пользователь {user.staff_number} {msg} '
        f'администратором {current_user.staff_number}'
    )
    flash(f'{user.full_name or user.staff_number} — {msg}.', 'success')
    return redirect(request.referrer or url_for('admin.users'))


def _has_notebook(topic):
    name = topic.notebook_filename
    if not name or os.path.basename(name) != name:
        return False
    return os.path.exists(os.path.join(Settings.COURSE_NB_DIR, name))


@admin_bp.route('/notebooks')
@admin_required
def notebooks():
    topics = [
        t for t in Topic.query.order_by(Topic.order).all()
        if _has_notebook(t)
    ]
    return render_template('admin_notebooks.html', topics=topics)


@admin_bp.route('/topic/<int:topic_id>/notebook', methods=['GET', 'POST'])
@admin_required
def notebook_config(topic_id):
    topic = Topic.query.get_or_404(topic_id)
    name = topic.notebook_filename
    if not _has_notebook(topic):
        flash('У темы нет доступного ноутбука.', 'info')
        return redirect(url_for('admin.notebooks'))

    path = os.path.join(Settings.COURSE_NB_DIR, name)
    cells = parse_notebook(path)
    answer_cells = [c for c in cells if c['kind'] == 'answer']
    tasks = {t.order: t for t in topic.notebook_tasks}

    if request.method == 'POST':
        kind = request.form.get('kind', '').strip()
        if kind in ('theory', 'test'):
            topic.notebook_kind = kind
        for c in answer_cells:
            task = tasks.get(c['order'])
            if task is None:
                task = NotebookTask(topic_id=topic.id, order=c['order'])
                db.session.add(task)
            task.accepted = request.form.get(
                f'accepted_{c["order"]}', ''
            ).strip()
        db.session.commit()
        logger.info(
            f'Практика темы {topic.code} обновлена администратором '
            f'{current_user.staff_number} (kind={topic.notebook_kind})'
        )
        flash('Настройки практики сохранены.', 'success')
        return redirect(url_for('admin.notebooks'))

    rows = [
        {
            'order': c['order'],
            'prompt': c['prompt'],
            'source': c['source'],
            'accepted': (tasks[c['order']].accepted
                         if c['order'] in tasks else ''),
        }
        for c in answer_cells
    ]
    return render_template(
        'admin_notebook.html', topic=topic, rows=rows,
        kind=topic.notebook_kind or 'theory',
    )
