import os
import tempfile

import pytest

_dbfd, _dbpath = tempfile.mkstemp(suffix=".db")
os.environ["DATABASE_URL"] = f"sqlite:///{_dbpath}"
os.environ["COURSE_PLAN_PATH"] = "/nonexistent.xlsx"

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import (  # noqa: E402
    Section, Topic, Question, AnswerOption, Users,
)


@pytest.fixture
def seeded():
    app = create_app()
    app.config.update(WTF_CSRF_ENABLED=False, TESTING=True)
    with app.app_context():
        db.drop_all()
        db.create_all()

        section = Section(number=1, title="Раздел A", order=1)
        db.session.add(section)
        db.session.flush()

        topic_a = Topic(
            section_id=section.id, code="1.1",
            title="Тема с тестом", order=1,
            html_content="<p>теория A</p>",
        )
        topic_b = Topic(
            section_id=section.id, code="1.2",
            title="Тема без теста", order=2,
            html_content="<p>теория B</p>",
        )
        db.session.add_all([topic_a, topic_b])
        db.session.flush()

        q = Question(topic_id=topic_a.id, text="Q1", order=1)
        db.session.add(q)
        db.session.flush()
        right = AnswerOption(
            question_id=q.id, letter="A", text="верно", is_correct=True
        )
        wrong = AnswerOption(
            question_id=q.id, letter="B", text="неверно", is_correct=False
        )
        db.session.add_all([right, wrong])

        admin = Users(
            full_name="Admin", staff_number="00000001",
            email="admin@example.com", status=1, is_verified=True,
        )
        listener = Users(
            full_name="User", staff_number="00000002",
            email="user@example.com", status=0, is_verified=True,
        )
        db.session.add_all([admin, listener])
        db.session.commit()

        ids = {
            "section": section.id,
            "topic_a": topic_a.id,
            "topic_b": topic_b.id,
            "question": q.id,
            "right_option": right.id,
            "admin": admin.id,
            "listener": listener.id,
        }
    yield app, ids


@pytest.fixture
def client(seeded):
    app, _ = seeded
    return app.test_client()


def login(client, user_id):
    with client.session_transaction() as s:
        s["_user_id"] = str(user_id)
