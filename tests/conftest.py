import os
import tempfile

import pytest

_dbfd, _dbpath = tempfile.mkstemp(suffix=".db")
os.environ["DATABASE_URL"] = f"sqlite:///{_dbpath}"
os.environ["COURSE_PLAN_PATH"] = "/nonexistent.xlsx"

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import (  # noqa: E402
    Section, Topic, TopicBlock, Question, AnswerOption, Users,
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

        # topic_a: 3 блока теории + мини-тесты для блоков 1 и 2
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

        db.session.add_all([
            TopicBlock(topic_id=topic_a.id, order=1,
                       html_content="<p>блок 1</p>"),
            TopicBlock(topic_id=topic_a.id, order=2,
                       html_content="<p>блок 2</p>"),
            TopicBlock(topic_id=topic_a.id, order=3,
                       html_content="<p>заключение</p>"),
            TopicBlock(topic_id=topic_b.id, order=1,
                       html_content="<p>теория B</p>"),
        ])

        q1 = Question(topic_id=topic_a.id, text="Q1", order=1, block=1)
        q2 = Question(topic_id=topic_a.id, text="Q2", order=2, block=2)
        db.session.add_all([q1, q2])
        db.session.flush()

        right1 = AnswerOption(
            question_id=q1.id, letter="A", text="верно", is_correct=True
        )
        right2 = AnswerOption(
            question_id=q2.id, letter="A", text="верно", is_correct=True
        )
        db.session.add_all([
            right1,
            AnswerOption(question_id=q1.id, letter="B",
                         text="неверно", is_correct=False),
            right2,
            AnswerOption(question_id=q2.id, letter="B",
                         text="неверно", is_correct=False),
        ])

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
            "q1": q1.id,
            "q2": q2.id,
            "right1": right1.id,
            "right2": right2.id,
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
