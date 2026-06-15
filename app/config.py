from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"

load_dotenv(ENV_FILE)


class Settings:
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key")

    SQLALCHEMY_DATABASE_URI: str = os.getenv(
        "DATABASE_URL", "sqlite:///graph_course.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False

    SESSION_TYPE: str = os.getenv("SESSION_TYPE", "filesystem")
    SESSION_PERMANENT: bool = True
    SESSION_LIFETIME_DAYS: int = int(os.getenv("SESSION_LIFETIME_DAYS", "3"))
    SESSION_FILE_DIR: str = os.getenv("SESSION_FILE_DIR", "./flask_session")

    # SMTP-релей для отправки кодов подтверждения.
    # Логин/пароль читаются ТОЛЬКО из .env (не коммитятся).
    SMTP_HOST: str = os.getenv("SMTP_HOST", "SMTP.omega.sbrf.ru")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "2525"))
    SMTP_USE_TLS: bool = os.getenv("SMTP_USE_TLS", "true").lower() in (
        "1", "true", "yes", "on"
    )
    SMTP_SENDER: str = os.getenv("SMTP_SENDER", "")
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")

    COURSE_PLAN_PATH: str = (
        os.getenv("COURSE_PLAN_PATH")
        or str(BASE_DIR / "content" / "course_plan.xlsx")
    )
    COURSE_DOCX_DIR: str = (
        os.getenv("COURSE_DOCX_DIR") or str(BASE_DIR / "content" / "docx")
    )
    COURSE_NB_DIR: str = (
        os.getenv("COURSE_NB_DIR") or str(BASE_DIR / "content" / "notebooks")
    )
    COURSE_VIDEO_DIR: str = (
        os.getenv("COURSE_VIDEO_DIR") or str(BASE_DIR / "content" / "videos")
    )

    # Бэкап БД (см. app/services/backup.py).
    BACKUP_DIR: str = (
        os.getenv("BACKUP_DIR") or str(BASE_DIR / "backups")
    )
    BACKUP_INTERVAL_HOURS: float = float(
        os.getenv("BACKUP_INTERVAL_HOURS", "24")
    )
    BACKUP_KEEP: int = int(os.getenv("BACKUP_KEEP", "7"))
    BACKUP_FIRST_DELAY_SECONDS: float = float(
        os.getenv("BACKUP_FIRST_DELAY_SECONDS", "5")
    )
