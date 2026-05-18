from flask import Blueprint, render_template
from flask_login import current_user

from app.models import Section, Topic
from app.progress import passed_topic_ids, section_progress

main_bp = Blueprint('main', __name__)


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
    return render_template(
        'index.html',
        sections=sections,
        progress=progress,
        passed_ids=passed_ids,
        sections_total=len(sections),
        topics_total=topics_total,
        practices_total=practices_total,
        overall=overall,
    )
