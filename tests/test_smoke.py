from app.extensions import db
from app.models import Section, Topic
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
        assert next_topic([section], {a.id}).id == b.id
        assert next_topic([section], {a.id, b.id}) is None


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
    assert "Раздел A" in authed


def test_profile_shows_progress(seeded, client):
    _, ids = seeded
    login(client, ids["listener"])
    r = client.get("/profile")
    assert r.status_code == 200
    assert "%" in r.get_data(as_text=True)
