from datetime import timedelta
from pathlib import Path

from flask import Flask
from flask_session import Session
from flask_wtf.csrf import CSRFProtect

from .config import Settings
from .extensions import db, login_manager
from .app_logger import logger
from app.models import Users, register_background_tasks

csrf = CSRFProtect()
sess = Session()


def create_app() -> Flask:
    app = Flask(
        __name__,
        static_folder='../assets',
        static_url_path='/assets',
    )

    app.config['SECRET_KEY'] = Settings.SECRET_KEY
    app.config['SQLALCHEMY_DATABASE_URI'] = Settings.SQLALCHEMY_DATABASE_URI
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = (
        Settings.SQLALCHEMY_TRACK_MODIFICATIONS
    )
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'connect_args': {'check_same_thread': False, 'timeout': 30}
    }
    app.config['SESSION_TYPE'] = Settings.SESSION_TYPE
    app.config['SESSION_PERMANENT'] = Settings.SESSION_PERMANENT
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(
        days=Settings.SESSION_LIFETIME_DAYS
    )
    app.config['SESSION_FILE_DIR'] = Settings.SESSION_FILE_DIR

    Path(app.config['SESSION_FILE_DIR']).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    sess.init_app(app)

    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Пожалуйста, войдите в систему'
    login_manager.login_message_category = 'warning'

    @login_manager.user_loader
    def load_user(user_id):
        return Users.query.get(int(user_id))

    from .routes.main_routes import main_bp
    from .routes.auth_routes import auth_bp
    from .routes.course_routes import course_bp
    from .routes.admin_routes import admin_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(course_bp)
    app.register_blueprint(admin_bp)

    with app.app_context():
        db.create_all()
        _ensure_schema()
        register_background_tasks(app)

    logger.info('Приложение Graph Course инициализировано')
    return app


def _ensure_schema() -> None:
    """Лёгкая миграция без потери данных: добавляет недостающие колонки
    в существующую БД (db.create_all не изменяет уже созданные таблицы).
    """
    from sqlalchemy import text

    cols = {
        row[1]
        for row in db.session.execute(
            text("PRAGMA table_info(test_attempt)")
        )
    }
    if cols and 'block' not in cols:
        db.session.execute(text(
            "ALTER TABLE test_attempt "
            "ADD COLUMN block INTEGER NOT NULL DEFAULT 1"
        ))
        db.session.commit()
        logger.info('Схема обновлена: test_attempt.block добавлена')

    topic_cols = {
        row[1]
        for row in db.session.execute(
            text("PRAGMA table_info(topic)")
        )
    }
    if topic_cols and 'notebook_kind' not in topic_cols:
        db.session.execute(text(
            "ALTER TABLE topic ADD COLUMN notebook_kind VARCHAR(10)"
        ))
        db.session.commit()
        logger.info('Схема обновлена: topic.notebook_kind добавлена')
    if topic_cols and 'docx_hash' not in topic_cols:
        db.session.execute(text(
            "ALTER TABLE topic ADD COLUMN docx_hash VARCHAR(64)"
        ))
        db.session.commit()
        logger.info('Схема обновлена: topic.docx_hash добавлена')

    q_cols = {
        row[1]
        for row in db.session.execute(
            text("PRAGMA table_info(question)")
        )
    }
    if q_cols and 'is_final' not in q_cols:
        db.session.execute(text(
            "ALTER TABLE question "
            "ADD COLUMN is_final BOOLEAN NOT NULL DEFAULT 0"
        ))
        db.session.commit()
        logger.info('Схема обновлена: question.is_final добавлена')
