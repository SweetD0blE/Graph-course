from sqlalchemy import text

from app.extensions import db
from app.models import Section, Topic, TestAttempt, Users
from app.progress import is_gradable, section_progress, next_topic
from tests.conftest import login


def test_progress_helpers(seeded):
    app, ids = seeded
    with app.app_context():
        a = db.session.get(Topic, ids["topic_a"])
        b = db.session.get(Topic, ids["topic_b"])
        section = db.session.get(Section, ids["section"])
        assert is_gradable(a) is True
        assert is_gradable(b) is False
        sp = section_progress(section, set())
        assert sp == {
            "topics": 2, "total_test": 1, "passed": 0, "percent": 0,
        }
        sp_done = section_progress(section, {a.id})
        assert sp_done["passed"] == 1 and sp_done["percent"] == 100
        assert next_topic([section], set()).id == a.id
        # topic_b — без теста: пропускается, не залипает
        assert next_topic([section], {a.id}) is None


def test_sqlite_wal(seeded):
    app, _ = seeded
    with app.app_context():
        mode = db.session.execute(text("PRAGMA journal_mode")).scalar()
        assert str(mode).lower() == "wal"


def test_two_users_independent_attempts(seeded):
    app, ids = seeded
    c1 = app.test_client()
    c2 = app.test_client()
    login(c1, ids["listener"])
    login(c2, ids["admin"])
    form = {f'q{ids["question"]}': str(ids["right_option"])}
    assert c1.post(
        f'/course/topic/{ids["topic_a"]}/test', data=form
    ).status_code == 200
    assert c2.post(
        f'/course/topic/{ids["topic_a"]}/test', data=form
    ).status_code == 200
    with app.app_context():
        rows = TestAttempt.query.filter_by(
            topic_id=ids["topic_a"]
        ).all()
        by_user = {r.user_id: r for r in rows}
        assert by_user[ids["listener"]].passed is True
        assert by_user[ids["admin"]].passed is True
        assert len(rows) == 2


def test_topic_feedback(seeded, client):
    _, ids = seeded
    login(client, ids["listener"])
    # завалить тест: не выбрать верный вариант
    client.post(f'/course/topic/{ids["topic_a"]}/test', data={})
    body = client.get(
        f'/course/topic/{ids["topic_a"]}'
    ).get_data(as_text=True)
    assert "тест не сдан" in body
    assert "Пройти тест" in body


def test_lock_then_admin_reset(seeded, client):
    _, ids = seeded
    login(client, ids["listener"])

    r = client.post(
        f'/course/topic/{ids["topic_a"]}/test',
        data={f'q{ids["question"]}': str(ids["right_option"])},
    )
    assert r.status_code == 200
    assert "тест сдан" in r.get_data(as_text=True)

    blocked = client.get(f'/course/topic/{ids["topic_a"]}/test')
    assert blocked.status_code == 302

    admin_client = client
    login(admin_client, ids["admin"])
    reset = admin_client.post(
        f'/admin/users/{ids["listener"]}/reset/{ids["topic_a"]}'
    )
    assert reset.status_code == 302

    login(client, ids["listener"])
    reopened = client.get(f'/course/topic/{ids["topic_a"]}/test')
    assert reopened.status_code == 200


def test_admin_gating(seeded, client):
    _, ids = seeded
    login(client, ids["listener"])
    assert client.get("/admin/users").status_code == 403
    login(client, ids["admin"])
    assert client.get("/admin/users").status_code == 200


def test_home_guest_and_authed(seeded, client):
    _, ids = seeded
    guest = client.get("/").get_data(as_text=True)
    assert "Войти" in guest

    login(client, ids["listener"])
    authed = client.get("/").get_data(as_text=True)
    assert "Следующая тема" in authed


def test_home_no_duplicate_program(seeded, client):
    _, ids = seeded
    login(client, ids["listener"])
    body = client.get("/").get_data(as_text=True)
    assert 'id="program"' not in body
    assert "Посмотреть программу" not in body
    assert ">Прогресс<" not in body
    assert "Следующая тема" in body


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


def test_profile_pretty(seeded, client):
    _, ids = seeded
    login(client, ids["listener"])
    r = client.get("/profile")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "hero__meta" in body
    assert "progress-bar" in body
    assert "К курсу" in body
