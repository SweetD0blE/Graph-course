from app.models import TestAttempt, Topic


def topic_test_blocks(topic):
    """Номера тест-блоков темы с настроенными ответами (≥1 is_correct)."""
    return {
        q.block for q in topic.questions
        if any(o.is_correct for o in q.options)
    }


def has_reading(topic):
    """Есть ли у темы теоретический материал для чтения."""
    return bool(topic.blocks) or bool((topic.html_content or '').strip())


def is_gradable(topic):
    """Тема «гейтит» прогресс: настроенный тест ИЛИ ознакомление."""
    if topic_test_blocks(topic):
        return True
    return has_reading(topic)


def passed_blocks(user):
    """Множество (topic_id, block) со сданными попытками.

    block=0 — отметка «Идти дальше» для ознакомительной темы.
    """
    if not user or not user.is_authenticated:
        return set()
    return {
        (r.topic_id, r.block)
        for r in TestAttempt.query.filter_by(
            user_id=user.id, passed=True
        ).all()
    }


def topic_passed(topic, user, passed_set=None):
    """Тема пройдена: все тест-блоки сданы, либо ознакомление отмечено."""
    if passed_set is None:
        passed_set = passed_blocks(user)
    tb = topic_test_blocks(topic)
    if tb:
        return all((topic.id, b) in passed_set for b in tb)
    if has_reading(topic):
        return (topic.id, 0) in passed_set
    return False


def passed_topic_ids(user):
    if not user or not user.is_authenticated:
        return set()
    blocks = passed_blocks(user)
    return {
        t.id for t in Topic.query.all()
        if topic_passed(t, user, blocks)
    }


def section_completed(section, passed_ids):
    """Раздел пройден: все гейтящие темы раздела в passed_ids."""
    gradable = [t for t in section.topics if is_gradable(t)]
    return bool(gradable) and all(t.id in passed_ids for t in gradable)


def next_topic(sections, passed_ids):
    for s in sections:
        for t in s.topics:
            if not is_gradable(t):
                continue
            if t.id in passed_ids:
                continue
            return t
    return None


def course_topic_states(sections, passed_ids):
    """Статус тем по сквозному фронтиру: 'passed' | 'current' | 'locked'.

    Темы без гейтинга (нет docx) — 'open' (доступны, не блокируют).
    Первая несданная гейтящая тема — 'current', дальше всё 'locked'.
    """
    states = {}
    blocked = False
    for s in sections:
        for t in s.topics:
            if not is_gradable(t):
                states[t.id] = 'open'
                continue
            if t.id in passed_ids:
                states[t.id] = 'passed'
            elif blocked:
                states[t.id] = 'locked'
            else:
                states[t.id] = 'current'
                blocked = True
    return states


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
