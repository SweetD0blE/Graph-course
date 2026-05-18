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

    OUTLOOK_SENDER: str = os.getenv("OUTLOOK_SENDER", "")

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
