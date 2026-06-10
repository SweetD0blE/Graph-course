import threading
from datetime import datetime

from flask_login import UserMixin

from app.extensions import db


class Employee(db.Model):
    """Справочник сотрудников. Источник — выгрузка СВА (SVA_persons.xlsx)."""

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100))
    staff_number = db.Column(db.String(8), unique=True, nullable=False)
    position = db.Column(db.String(150))
    department = db.Column(db.String(150))
    email = db.Column(db.String(100), unique=True)


class Users(db.Model, UserMixin):
    """Зарегистрированные пользователи портала.

    status: 0 — обычный пользователь, 1 — администратор.
    Аутентификация — по табельному номеру и коду подтверждения из почты.
    """

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100))
    staff_number = db.Column(db.String(8), unique=True, nullable=False)
    position = db.Column(db.String(150))
    department = db.Column(db.String(150))
    email = db.Column(db.String(100), unique=True)

    status = db.Column(db.Integer, nullable=False, default=0)
    verification_code = db.Column(db.String(6))
    is_verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def populate_from_employee(self, employee: "Employee") -> None:
        """Заполняет поля пользователя из записи Employee."""
        self.full_name = employee.full_name
        self.staff_number = employee.staff_number
        self.position = employee.position
        self.department = employee.department
        self.email = employee.email

    def get_id(self) -> str:
        return str(self.id)


class Section(db.Model):
    """Раздел курса (колонки «№» и «Раздел» в плане курса)."""

    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.Integer, unique=True, nullable=False)
    title = db.Column(db.String(255))
    order = db.Column(db.Integer, default=0)

    topics = db.relationship(
        "Topic",
        backref="section",
        order_by="Topic.order",
        cascade="all, delete-orphan",
    )


class Topic(db.Model):
    """Тема внутри раздела. html_content — теория без блоков «Тест»."""

    id = db.Column(db.Integer, primary_key=True)
    section_id = db.Column(
        db.Integer, db.ForeignKey("section.id"), nullable=False
    )
    code = db.Column(db.String(20), unique=True, nullable=False)
    title = db.Column(db.String(255))
    content_form = db.Column(db.String(100))
    assessment = db.Column(db.String(255))
    outcome = db.Column(db.Text)
    doc_filename = db.Column(db.String(255))
    notebook_filename = db.Column(db.String(255))
    notebook_kind = db.Column(db.String(10))  # устар.; не используется
    docx_hash = db.Column(db.String(64))
    html_content = db.Column(db.Text)
    order = db.Column(db.Integer, default=0)

    questions = db.relationship(
        "Question",
        backref="topic",
        order_by="Question.order",
        cascade="all, delete-orphan",
    )
    blocks = db.relationship(
        "TopicBlock",
        backref="topic",
        order_by="TopicBlock.order",
        cascade="all, delete-orphan",
    )


class TopicBlock(db.Model):
    """Сегмент теории темы. order — порядковый номер блока чтения."""

    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(
        db.Integer, db.ForeignKey("topic.id"), nullable=False
    )
    order = db.Column(db.Integer, nullable=False, default=1)
    html_content = db.Column(db.Text)


class Question(db.Model):
    """Вопрос теста темы. block — номер тест-блока внутри docx,
    is_final — вопрос из блока «Финальный тест».
    """

    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(
        db.Integer, db.ForeignKey("topic.id"), nullable=False
    )
    order = db.Column(db.Integer, default=0)
    block = db.Column(db.Integer, default=1)
    is_final = db.Column(db.Boolean, nullable=False, default=False)
    text = db.Column(db.Text, nullable=False)

    options = db.relationship(
        "AnswerOption",
        backref="question",
        order_by="AnswerOption.letter",
        cascade="all, delete-orphan",
    )


class AnswerOption(db.Model):
    """Вариант ответа. is_correct проставляет администратор в интерфейсе."""

    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(
        db.Integer, db.ForeignKey("question.id"), nullable=False
    )
    letter = db.Column(db.String(2), nullable=False)
    text = db.Column(db.Text, nullable=False)
    is_correct = db.Column(db.Boolean, nullable=False, default=False)


class TestAttempt(db.Model):
    """Журнал попыток прохождения теста темы."""

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False
    )
    topic_id = db.Column(
        db.Integer, db.ForeignKey("topic.id"), nullable=False
    )
    block = db.Column(db.Integer, nullable=False, default=1)
    score = db.Column(db.Integer, nullable=False, default=0)
    passed = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


def run_import_in_thread(app) -> None:
    """Фоновый импорт сотрудников и плана курса при старте приложения."""
    with app.app_context():
        from app.app_logger import logger

        try:
            from app.utils import load_sva_persons

            load_sva_persons(db)
        except Exception:
            logger.exception("Фоновый импорт сотрудников провален")

        try:
            from app.utils import load_course_plan

            load_course_plan(db)
        except Exception:
            logger.exception("Фоновый импорт плана курса провален")


def register_background_tasks(app) -> None:
    """Запускает фоновую загрузку данных в отдельном потоке."""
    thread = threading.Thread(target=run_import_in_thread, args=(app,), daemon=True)
    thread.start()
