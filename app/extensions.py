"""Расширения Flask, общие для всего приложения.

Инициализируются в фабрике create_app() через .init_app().
"""

import sqlite3

from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from sqlalchemy import event
from sqlalchemy.engine import Engine

db: SQLAlchemy = SQLAlchemy()
login_manager: LoginManager = LoginManager()


@event.listens_for(Engine, "connect")
def _sqlite_pragmas(dbapi_conn, _rec):
    """WAL + busy_timeout: читатели не блокируют писателя, при блокировке
    ждём вместо мгновенной ошибки «database is locked»."""
    if isinstance(dbapi_conn, sqlite3.Connection):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=30000")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.close()
