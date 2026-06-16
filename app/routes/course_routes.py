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
    next_topic as compute_next_topic, section_completed,
    course_topic_states, topic_passed, has_reading,
)
from app.services.app_logger import logger

course_bp = Blueprint('course', __name__, url_prefix='/course')


@course_bp.route('/')
@login_required
def index():
    sections = Section.query.order_by(Section.order).all()
    passed_ids = passed_topic_ids(current_user)
    progress = {
        s.id: section_progress(s, passed_ids) for s in sections
    }
    section_states = {}
    prev_ok = True
    for idx, s in enumerate(sections):
        section_states[s.id] = 'opened' if (idx == 0 or prev_ok) else 'locked'
        prev_ok = prev_ok and section_completed(s, passed_ids)
    topic_states = course_topic_states(sections, passed_ids)
    return render_template(
        'course/list.html',
        sections=sections,
        progress=progress,
        section_states=section_states,
        topic_states=topic_states,
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
    video_available = bool(
        topic.video_filename
        and os.path.exists(
            os.path.join(Settings.COURSE_VIDEO_DIR, topic.video_filename)
        )
    )
    subtitle_available = bool(
        topic.subtitle_filename
        and os.path.exists(
            os.path.join(Settings.COURSE_VIDEO_DIR, topic.subtitle_filename)
        )
    )
    gradable_blocks = topic_test_blocks(topic)
    all_passed = passed_blocks(current_user)
    passed = {b for (tid, b) in all_passed if tid == topic.id}
    final_blocks = {
        q.block for q in topic.questions if q.is_final
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
            'is_final': n in final_blocks,
            'status': status,
            'questions': (
                q_by_block.get(n, [])
                if status == 'open' and has_test else []
            ),
        })
        if unlocked:
            unlocked = (not has_test) or block_done

    # Вопросы в docx есть, но админ ещё не разметил ответы —
    # «Идти дальше» не показываем, чтобы тест нельзя было обойти.
    pending = bool(topic.questions) and not gradable_blocks
    reading_only = not topic.questions and has_reading(topic)
    topic_done = topic_passed(topic, current_user, all_passed)
    next_url = _next_topic_url(topic) if topic_done else None
    return render_template(
        'course/topic.html',
        topic=topic,
        nb_available=nb_available,
        video_available=video_available,
        subtitle_available=subtitle_available,
        stages=stages,
        reading_only=reading_only,
        pending=pending,
        topic_done=topic_done,
        next_url=next_url,
    )


@course_bp.route(
    '/topic/<int:topic_id>/block/<int:block>/test', methods=['POST']
)
@login_required
def block_test(topic_id, block):
    topic = Topic.query.get_or_404(topic_id)
    anchor = url_for('course.topic', topic_id=topic.id) + f'#block-{block}'
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    def respond(message, category, *, passed=False, score=None, ok=True,
                topic_done=False, next_url=None):
        if is_ajax:
            return jsonify(
                ok=ok, passed=passed, score=score, message=message,
                topic_done=topic_done, next_url=next_url,
            )
        flash(message, category)
        return redirect(anchor)

    questions = [
        q for q in topic.questions
        if q.block == block and any(o.is_correct for o in q.options)
    ]
    if not questions:
        return respond('Тест недоступен.', 'warning', ok=False)

    is_final = any(q.is_final for q in questions)

    passed_here = {
        b for (tid, b) in passed_blocks(current_user) if tid == topic.id
    }
    prior = {b for b in topic_test_blocks(topic) if b < block}
    if not prior.issubset(passed_here):
        return respond(
            'Сначала пройдите предыдущие тесты.', 'warning', ok=False,
        )

    if block in passed_here:
        return respond('Этот тест уже пройден.', 'info', ok=False)

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
        f'{"Финальный тест" if is_final else "Тест"} {topic.code}'
        f'/блок {block}: пользователь '
        f'{current_user.staff_number} — {score}% — '
        f'{"сдан" if passed else "не сдан"}'
    )
    if passed:
        done = topic_passed(topic, current_user)
        message = (
            'Финальный тест пройден — тема завершена.' if is_final
            else 'Тест пройден — следующий блок открыт.'
        )
        return respond(
            message, 'success',
            passed=True, score=score,
            topic_done=done,
            next_url=_next_topic_url(topic) if done else None,
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


@course_bp.route('/video/<int:topic_id>')
@login_required
def video(topic_id):
    """Инлайновая отдача mp4 с поддержкой Range-запросов для перемотки."""
    topic = Topic.query.get_or_404(topic_id)
    name = topic.video_filename
    if not name or os.path.basename(name) != name:
        abort(404)
    video_dir = os.path.abspath(Settings.COURSE_VIDEO_DIR)
    if not os.path.exists(os.path.join(video_dir, name)):
        abort(404)
    return send_from_directory(
        video_dir, name,
        as_attachment=False, conditional=True, mimetype='video/mp4',
    )


@course_bp.route('/subtitle/<int:topic_id>')
@login_required
def subtitle(topic_id):
    """Инлайновая отдача WebVTT-субтитров рядом с видео темы."""
    topic = Topic.query.get_or_404(topic_id)
    name = topic.subtitle_filename
    if not name or os.path.basename(name) != name:
        abort(404)
    video_dir = os.path.abspath(Settings.COURSE_VIDEO_DIR)
    if not os.path.exists(os.path.join(video_dir, name)):
        abort(404)
    return send_from_directory(
        video_dir, name,
        as_attachment=False, mimetype='text/vtt',
    )


def _next_topic_url(current_topic):
    """URL следующей не пройденной темы; None — если курс пройден."""
    sections = Section.query.order_by(Section.order).all()
    passed = passed_topic_ids(current_user) | {current_topic.id}
    nxt = compute_next_topic(sections, passed)
    return url_for('course.topic', topic_id=nxt.id) if nxt else None


@course_bp.route('/topic/<int:topic_id>/complete', methods=['POST'])
@login_required
def topic_complete(topic_id):
    """Отметка «Идти дальше» для ознакомительной темы (без тестов)."""
    topic = Topic.query.get_or_404(topic_id)
    if topic.questions or not has_reading(topic):
        # Вопросы есть (даже ненастроенные) — тему нельзя пройти чтением.
        return jsonify(
            ok=False, topic_done=False, next_url=None,
            message='Для этой темы нужно пройти тест.',
        )
    exists = TestAttempt.query.filter_by(
        user_id=current_user.id, topic_id=topic.id, block=0, passed=True,
    ).first()
    if not exists:
        db.session.add(TestAttempt(
            user_id=current_user.id, topic_id=topic.id,
            block=0, score=100, passed=True,
        ))
        db.session.commit()
        logger.info(
            f'Тема {topic.code} (ознакомление) отмечена пользователем '
            f'{current_user.staff_number}'
        )
    return jsonify(
        ok=True, topic_done=True,
        next_url=_next_topic_url(topic),
        message='Тема пройдена.',
    )
