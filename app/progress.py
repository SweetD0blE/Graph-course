from app.models import TestAttempt, Topic, NotebookAttempt


def is_gradable(topic):
    """Тема «гейтит» прогресс через ноутбук или мини-тесты."""
    if topic.notebook_kind == 'theory':
        return True
    if topic.notebook_kind == 'test':
        return any(
            (t.accepted or '').strip() for t in topic.notebook_tasks
        )
    return any(
        any(o.is_correct for o in q.options) for q in topic.questions
    )


def topic_test_blocks(topic):
    """Номера блоков темы, у которых есть настроенный мини-тест."""
    return {
        q.block for q in topic.questions
        if any(o.is_correct for o in q.options)
    }


def passed_blocks(user):
    """Множество (topic_id, block) со сданными на 100% мини-тестами."""
    if not user or not user.is_authenticated:
        return set()
    return {
        (r.topic_id, r.block)
        for r in TestAttempt.query.filter_by(
            user_id=user.id, passed=True
        ).all()
    }


def notebook_completed(topic, user):
    """Тема засчитана через ноутбук."""
    if not topic.notebook_kind or not user or not user.is_authenticated:
        return False
    if topic.notebook_kind == 'theory':
        return NotebookAttempt.query.filter_by(
            user_id=user.id, topic_id=topic.id,
            cell_order=0, passed=True,
        ).first() is not None
    tasks = topic.notebook_tasks
    if not tasks:
        return False
    done = {
        a.cell_order for a in NotebookAttempt.query.filter_by(
            user_id=user.id, topic_id=topic.id, passed=True,
        ).all()
    }
    return all(t.order in done for t in tasks)


def topic_passed(topic, user, passed_set):
    """Тема пройдена: по ноутбуку, либо по мини-тестам (фолбэк)."""
    if topic.notebook_kind:
        return notebook_completed(topic, user)
    tb = topic_test_blocks(topic)
    return bool(tb) and all((topic.id, b) in passed_set for b in tb)


def passed_topic_ids(user):
    if not user or not user.is_authenticated:
        return set()
    blocks = passed_blocks(user)
    return {
        t.id for t in Topic.query.all()
        if topic_passed(t, user, blocks)
    }


def next_topic(sections, passed_ids):
    for s in sections:
        for t in s.topics:
            if not is_gradable(t):
                continue
            if t.id in passed_ids:
                continue
            return t
    return None


def section_progress(section, passed_ids):
    test_topics = [t for t in section.topics if is_gradable(t)]
    total_test = len(test_topics)
    passed = sum(1 for t in test_topics if t.id in passed_ids)
    return {
        'topics': len(section.topics),
        'total_test': total_test,
        'passed': passed,
        'percent': round(passed / total_test * 100) if total_test else 0,
    }
