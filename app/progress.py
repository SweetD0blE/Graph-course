from app.models import TestAttempt, Topic


def is_gradable(topic):
    return any(
        any(o.is_correct for o in q.options) for q in topic.questions
    )


def topic_test_blocks(topic):
    """Номера блоков темы, у которых есть настроенный тест."""
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


def topic_passed(topic, passed_set):
    """Тема пройдена ⇔ сданы все её настроенные мини-блоки."""
    tb = topic_test_blocks(topic)
    return bool(tb) and all(
        (topic.id, b) in passed_set for b in tb
    )


def passed_topic_ids(user):
    passed = passed_blocks(user)
    if not passed:
        return set()
    return {
        t.id for t in Topic.query.all() if topic_passed(t, passed)
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
