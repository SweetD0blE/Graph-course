import os

from flask import (
    Blueprint, render_template, abort, request, redirect, url_for, flash,
    send_from_directory,
)
from flask_login import login_required, current_user

from app.extensions import db
from app.config import Settings
from app.models import Section, Topic, Question, AnswerOption, TestAttempt
from app.progress import passed_topic_ids, section_progress
from app.app_logger import logger

course_bp = Blueprint('course', __name__, url_prefix='/course')


@course_bp.route('/')
@login_required
def index():
    sections = Section.query.order_by(Section.order).all()
    passed_ids = passed_topic_ids(current_user)
    progress = {
        s.id: section_progress(s, passed_ids) for s in sections
    }
    return render_template(
        'course.html',
        sections=sections,
        progress=progress,
        passed_ids=passed_ids,
    )


@course_bp.route('/topic/<int:topic_id>')
@login_required
def topic(topic_id):
    topic = Topic.query.get_or_404(topic_id)
    has_test = len(topic.questions) > 0
    nb_available = bool(
        topic.notebook_filename
        and os.path.exists(
            os.path.join(Settings.COURSE_NB_DIR, topic.notebook_filename)
        )
    )
    attempts = TestAttempt.query.filter_by(
        user_id=current_user.id, topic_id=topic_id
    ).all()
    passed = any(a.passed for a in attempts)
    best = max((a.score for a in attempts), default=0)
    return render_template(
        'topic.html',
        topic=topic,
        has_test=has_test,
        nb_available=nb_available,
        passed=passed,
        best=best,
        attempts=len(attempts),
    )


@course_bp.route('/topic/<int:topic_id>/test', methods=['GET', 'POST'])
@login_required
def test(topic_id):
    topic = Topic.query.get_or_404(topic_id)
    questions = topic.questions
    if not questions:
        flash('У этой темы пока нет теста.', 'info')
        return redirect(url_for('course.topic', topic_id=topic.id))

    gradable = [
        q for q in questions
        if any(o.is_correct for o in q.options)
    ]
    if not gradable:
        flash(
            'Тест ещё настраивается администратором — '
            'правильные ответы не заданы.',
            'warning',
        )
        return redirect(url_for('course.topic', topic_id=topic.id))

    if topic.id in passed_topic_ids(current_user):
        flash(
            'Вы уже прошли этот тест на 100%. '
            'Повторное прохождение недоступно.',
            'info',
        )
        return redirect(url_for('course.topic', topic_id=topic.id))

    if request.method == 'POST':
        correct = 0
        review = []
        for q in gradable:
            selected = set(request.form.getlist(f'q{q.id}'))
            right = {
                str(o.id) for o in q.options if o.is_correct
            }
            is_ok = selected == right
            if is_ok:
                correct += 1
            review.append({'question': q, 'ok': is_ok})

        total = len(gradable)
        score = round(correct / total * 100)
        passed = score == 100

        if topic.id in passed_topic_ids(current_user):
            flash(
                'Вы уже прошли этот тест на 100%. '
                'Повторное прохождение недоступно.',
                'info',
            )
            return redirect(url_for('course.topic', topic_id=topic.id))

        attempt = TestAttempt(
            user_id=current_user.id,
            topic_id=topic.id,
            score=score,
            passed=passed,
        )
        db.session.add(attempt)
        db.session.commit()
        logger.info(
            f'Тест темы {topic.code}: пользователь '
            f'{current_user.staff_number} — {score}% — '
            f'{"сдан" if passed else "не сдан"}'
        )
        return render_template(
            'test_result.html',
            topic=topic,
            score=score,
            passed=passed,
            correct=correct,
            total=total,
            review=review,
        )

    return render_template('test.html', topic=topic, questions=gradable)


@course_bp.route('/notebook/<int:topic_id>')
@login_required
def notebook(topic_id):
    topic = Topic.query.get_or_404(topic_id)
    name = topic.notebook_filename
    if not name or os.path.basename(name) != name:
        abort(404)
    nb_dir = os.path.abspath(Settings.COURSE_NB_DIR)
    if not os.path.exists(os.path.join(nb_dir, name)):
        abort(404)
    return send_from_directory(nb_dir, name, as_attachment=True)
