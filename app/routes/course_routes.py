import os

from flask import (
    Blueprint, render_template, abort, request, redirect, url_for, flash,
    send_from_directory, jsonify,
)
from flask_login import login_required, current_user

from app.extensions import db
from app.config import Settings
from app.models import Section, Topic, TestAttempt
from app.progress import (
    passed_topic_ids, section_progress, passed_blocks, topic_test_blocks,
)
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
    nb_available = bool(
        topic.notebook_filename
        and os.path.exists(
            os.path.join(Settings.COURSE_NB_DIR, topic.notebook_filename)
        )
    )
    gradable_blocks = topic_test_blocks(topic)
    passed = {
        b for (tid, b) in passed_blocks(current_user) if tid == topic.id
    }

    q_by_block = {}
    for q in topic.questions:
        q_by_block.setdefault(q.block, []).append(q)

    blocks = list(topic.blocks)
    if not blocks:
        from types import SimpleNamespace
        blocks = [SimpleNamespace(order=1, html_content=topic.html_content)]

    stages = []
    unlocked = True
    for blk in blocks:
        n = blk.order
        has_test = n in gradable_blocks
        block_done = n in passed
        if not unlocked:
            status = 'locked'
        elif has_test and block_done:
            status = 'done'
        else:
            status = 'open'
        stages.append({
            'order': n,
            'html': blk.html_content or '',
            'has_test': has_test,
            'status': status,
            'questions': (
                q_by_block.get(n, [])
                if status == 'open' and has_test else []
            ),
        })
        if unlocked:
            unlocked = (not has_test) or block_done

    topic_done = bool(gradable_blocks) and gradable_blocks.issubset(passed)
    return render_template(
        'topic.html',
        topic=topic,
        nb_available=nb_available,
        stages=stages,
        topic_done=topic_done,
    )


@course_bp.route(
    '/topic/<int:topic_id>/block/<int:block>/test', methods=['POST']
)
@login_required
def block_test(topic_id, block):
    topic = Topic.query.get_or_404(topic_id)
    anchor = url_for('course.topic', topic_id=topic.id) + f'#block-{block}'
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    def respond(message, category, *, passed=False, score=None, ok=True):
        if is_ajax:
            return jsonify(
                ok=ok, passed=passed, score=score, message=message,
            )
        flash(message, category)
        return redirect(anchor)

    questions = [
        q for q in topic.questions
        if q.block == block and any(o.is_correct for o in q.options)
    ]
    if not questions:
        return respond('Мини-тест недоступен.', 'warning', ok=False)

    passed_here = {
        b for (tid, b) in passed_blocks(current_user) if tid == topic.id
    }
    prior = {b for b in topic_test_blocks(topic) if b < block}
    if not prior.issubset(passed_here):
        return respond(
            'Сначала пройдите предыдущие мини-тесты.', 'warning', ok=False,
        )

    if block in passed_here:
        return respond('Этот мини-тест уже пройден.', 'info', ok=False)

    correct = 0
    for q in questions:
        selected = set(request.form.getlist(f'q{q.id}'))
        right = {str(o.id) for o in q.options if o.is_correct}
        if selected == right:
            correct += 1

    total = len(questions)
    score = round(correct / total * 100)
    passed = score == 100

    db.session.add(TestAttempt(
        user_id=current_user.id,
        topic_id=topic.id,
        block=block,
        score=score,
        passed=passed,
    ))
    db.session.commit()
    logger.info(
        f'Мини-тест {topic.code}/блок {block}: пользователь '
        f'{current_user.staff_number} — {score}% — '
        f'{"сдан" if passed else "не сдан"}'
    )
    if passed:
        return respond(
            'Мини-тест пройден — следующий блок открыт.', 'success',
            passed=True, score=score,
        )
    return respond(
        f'Не сдан: {score}%. Попробуйте снова.', 'warning',
        passed=False, score=score,
    )


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
