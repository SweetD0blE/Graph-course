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


def run_import_in_thread(app) -> None:
    """Фоновый импорт сотрудников из SVA при старте приложения."""
    with app.app_context():
        try:
            from app.utils import load_sva_persons

            load_sva_persons(db)
        except Exception as e:  # noqa: BLE001
            print(f"[Импорт сотрудников] Ошибка: {e}")


def register_background_tasks(app) -> None:
    """Запускает фоновую задачу импорта сотрудников в отдельном потоке."""
    thread = threading.Thread(target=run_import_in_thread, args=(app,), daemon=True)
    thread.start()
