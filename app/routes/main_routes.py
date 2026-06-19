from flask import Blueprint, render_template
from flask_login import current_user

from app.models import Section, Topic
from app.progress import (
    passed_topic_ids, section_progress, next_topic,
    course_topic_states, section_completed,
)

main_bp = Blueprint('main', __name__)


def _is_admin(user):
    """Тот же признак, что admin_required в admin_routes."""
    return user.is_authenticated and getattr(user, 'status', 0) == 1


@main_bp.route('/')
def index():
    sections = Section.query.order_by(Section.order).all()
    topics_total = Topic.query.count()
    practices_total = Topic.query.filter(
        Topic.notebook_filename.isnot(None)
    ).count()
    passed_ids = passed_topic_ids(current_user)
    progress = {s.id: section_progress(s, passed_ids) for s in sections}
    tt = sum(p['total_test'] for p in progress.values())
    pp = sum(p['passed'] for p in progress.values())
    overall = round(pp / tt * 100) if tt else 0
    nxt = next_topic(sections, passed_ids)

    # Статусы как на /course/ (та же логика гейтинга).
    section_states = {}
    prev_ok = True
    for idx, s in enumerate(sections):
        section_states[s.id] = 'opened' if (idx == 0 or prev_ok) else 'locked'
        prev_ok = prev_ok and section_completed(s, passed_ids)
    topic_states = course_topic_states(sections, passed_ids)
    # Админ видит всё открытым (без замков).
    if _is_admin(current_user):
        section_states = {s.id: 'opened' for s in sections}
        topic_states = {
            t.id: ('passed' if t.id in passed_ids else 'open')
            for s in sections for t in s.topics
        }

    return render_template(
        'main/index.html',
        sections=sections,
        progress=progress,
        passed_ids=passed_ids,
        sections_total=len(sections),
        topics_total=topics_total,
        practices_total=practices_total,
        overall=overall,
        next_topic=nxt,
        section_states=section_states,
        topic_states=topic_states,
    )
