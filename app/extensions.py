"""Расширения Flask, общие для всего приложения.

Инициализируются в фабрике create_app() через .init_app().
"""

from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

db: SQLAlchemy = SQLAlchemy()
login_manager: LoginManager = LoginManager()
