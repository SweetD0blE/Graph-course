from sqlalchemy import text

from app.extensions import db
from app.models import Section, Topic, TestAttempt, Users
from app.progress import (
    is_gradable, section_progress, next_topic,
    topic_test_blocks, topic_passed, passed_topic_ids,
)
from tests.conftest import login


def _pass_block(client, ids, block):
    q = ids["q1"] if block == 1 else ids["q2"]
    opt = ids["right1"] if block == 1 else ids["right2"]
    return client.post(
        f'/course/topic/{ids["topic_a"]}/block/{block}/test',
        data={f'q{q}': str(opt)},
    )


def test_progress_helpers(seeded):
    app, ids = seeded
    with app.app_context():
        a = db.session.get(Topic, ids["topic_a"])
        b = db.session.get(Topic, ids["topic_b"])
        section = db.session.get(Section, ids["section"])
        assert is_gradable(a) is True
        assert is_gradable(b) is False
        assert topic_test_blocks(a) == {1, 2}
        assert topic_passed(a, set()) is False
        assert topic_passed(a, {(a.id, 1)}) is False
        assert topic_passed(a, {(a.id, 1), (a.id, 2)}) is True

        sp = section_progress(section, set())
        assert sp == {
            "topics": 2, "total_test": 1, "passed": 0, "percent": 0,
        }
        sp_done = section_progress(section, {a.id})
        assert sp_done["passed"] == 1 and sp_done["percent"] == 100
        assert next_topic([section], set()).id == a.id
        assert next_topic([section], {a.id}) is None


def test_block_unlock_flow(seeded, client):
    _, ids = seeded
    login(client, ids["listener"])
    url = f'/course/topic/{ids["topic_a"]}'

    body = client.get(url).get_data(as_text=True)
    assert "Мини-тест 1" in body
    assert "Блок закрыт" in body          # блок 2 заперт
    assert "Мини-тест 2" not in body

    _pass_block(client, ids, 1)
    body = client.get(url).get_data(as_text=True)
    assert "Мини-тест пройден" in body    # блок 1 — done
    assert "Мини-тест 2" in body          # блок 2 открылся
    assert "Тема пройдена" not in body

    _pass_block(client, ids, 2)
    body = client.get(url).get_data(as_text=True)
    assert "Тема пройдена" in body


def test_block_test_gating(seeded, client):
    _, ids = seeded
    login(client, ids["listener"])
    # Попытка сдать блок 2 до блока 1 — не должна засчитаться
    _pass_block(client, ids, 2)
    with client.application.app_context():
        rows = TestAttempt.query.filter_by(
            topic_id=ids["topic_a"], block=2
        ).all()
        assert rows == []


def test_minitest_locked_after_pass(seeded, client):
    _, ids = seeded
    login(client, ids["listener"])
    _pass_block(client, ids, 1)
    _pass_block(client, ids, 1)   # повторная сдача
    with client.application.app_context():
        rows = TestAttempt.query.filter_by(
            topic_id=ids["topic_a"], block=1
        ).all()
        assert len(rows) == 1     # вторая отправка отклонена


def test_topic_passed_only_after_all_blocks(seeded, client):
    _, ids = seeded
    login(client, ids["listener"])
    _pass_block(client, ids, 1)
    with client.application.app_context():
        user = db.session.get(Users, ids["listener"])
        assert ids["topic_a"] not in passed_topic_ids(user)
    _pass_block(client, ids, 2)
    with client.application.app_context():
        user = db.session.get(Users, ids["listener"])
        assert ids["topic_a"] in passed_topic_ids(user)


def test_old_test_route_removed(seeded, client):
    _, ids = seeded
    login(client, ids["listener"])
    assert client.get(
        f'/course/topic/{ids["topic_a"]}/test'
    ).status_code == 404


def test_admin_reset_clears_blocks(seeded, client):
    _, ids = seeded
    login(client, ids["listener"])
    _pass_block(client, ids, 1)
    login(client, ids["admin"])
    client.post(
        f'/admin/users/{ids["listener"]}/reset/{ids["topic_a"]}'
    )
    with client.application.app_context():
        rows = TestAttempt.query.filter_by(
            user_id=ids["listener"], topic_id=ids["topic_a"]
        ).all()
        assert rows == []


def test_sqlite_wal_and_block_column(seeded):
    app, _ = seeded
    with app.app_context():
        mode = db.session.execute(text("PRAGMA journal_mode")).scalar()
        assert str(mode).lower() == "wal"
        cols = {
            row[1] for row in db.session.execute(
                text("PRAGMA table_info(test_attempt)")
            )
        }
        assert "block" in cols


def test_two_users_independent_attempts(seeded):
    app, ids = seeded
    c1, c2 = app.test_client(), app.test_client()
    login(c1, ids["listener"])
    login(c2, ids["admin"])
    _pass_block(c1, ids, 1)
    _pass_block(c2, ids, 1)
    with app.app_context():
        rows = TestAttempt.query.filter_by(
            topic_id=ids["topic_a"], block=1
        ).all()
        by_user = {r.user_id: r for r in rows}
        assert by_user[ids["listener"]].passed is True
        assert by_user[ids["admin"]].passed is True
        assert len(rows) == 2


def test_admin_gating(seeded, client):
    _, ids = seeded
    login(client, ids["listener"])
    assert client.get("/admin/users").status_code == 403
    login(client, ids["admin"])
    assert client.get("/admin/users").status_code == 200


def test_set_role_promote_demote(seeded, client):
    _, ids = seeded
    login(client, ids["admin"])
    client.post(f'/admin/users/{ids["listener"]}/role')
    with client.application.app_context():
        assert db.session.get(Users, ids["listener"]).status == 1
    client.post(f'/admin/users/{ids["listener"]}/role')
    with client.application.app_context():
        assert db.session.get(Users, ids["listener"]).status == 0


def test_last_admin_protected(seeded, client):
    _, ids = seeded
    login(client, ids["admin"])
    client.post(f'/admin/users/{ids["admin"]}/role')
    with client.application.app_context():
        assert db.session.get(Users, ids["admin"]).status == 1


def test_home_no_duplicate_program(seeded, client):
    _, ids = seeded
    login(client, ids["listener"])
    body = client.get("/").get_data(as_text=True)
    assert 'id="program"' not in body
    assert "Следующая тема" in body


def test_profile_pretty(seeded, client):
    _, ids = seeded
    login(client, ids["listener"])
    r = client.get("/profile")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "hero__meta" in body
    assert "К курсу" in body
