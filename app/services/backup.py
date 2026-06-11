"""Ежедневный бэкап SQLite-БД с ротацией.

Делается через `sqlite3.Connection.backup()` — атомарный горячий
снапшот, безопасный для WAL-режима (учитывает -wal/-shm). Простой
`shutil.copy(.db)` для WAL даёт неконсистентный файл.

Планировщик: `threading.Timer`, каждый таймер сам ставит следующий
после успешного выполнения. Первый бэкап — через несколько секунд
после старта (быстрая обратная связь в логе), далее — раз в
`BACKUP_INTERVAL_HOURS` часов. Ротация — оставить `BACKUP_KEEP`
последних файлов по маске.
"""

import os
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

from app.config import Settings
from app.services.app_logger import logger


_BACKUP_PREFIX = "graph_course-"
_BACKUP_SUFFIX = ".db"


def _list_backups(backup_dir: Path):
    return sorted(
        backup_dir.glob(f"{_BACKUP_PREFIX}*{_BACKUP_SUFFIX}")
    )


def make_backup(db_path: str, backup_dir: str, keep: int) -> Path | None:
    """Снимает копию db_path в backup_dir/<prefix>-<ts>.db; чистит лишнее.

    Возвращает Path созданного файла или None при отсутствии исходной БД.
    """
    src = Path(db_path)
    if not src.exists():
        logger.warning(f"Бэкап: исходная БД не найдена ({src})")
        return None

    out_dir = Path(backup_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    dst = out_dir / f"{_BACKUP_PREFIX}{ts}{_BACKUP_SUFFIX}"

    # Горячая копия через native sqlite backup API.
    src_conn = sqlite3.connect(str(src))
    try:
        dst_conn = sqlite3.connect(str(dst))
        try:
            with dst_conn:
                src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
    finally:
        src_conn.close()

    # Ротация: оставить keep самых свежих по имени (сортируется как дата).
    files = _list_backups(out_dir)
    excess = files[:-keep] if keep > 0 else []
    for old in excess:
        try:
            old.unlink()
        except OSError as e:  # noqa: PERF203
            logger.warning(f"Бэкап: не удалось удалить старый {old.name}: {e}")

    logger.info(
        f"Бэкап создан: {dst.name} "
        f"(всего хранится: {min(len(files), keep)})"
    )
    return dst


def _resolve_db_path(app) -> str | None:
    """Достаёт абсолютный путь к sqlite-файлу из engine.url."""
    try:
        from app.extensions import db
        url = db.engine.url
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Бэкап: не удалось получить URL БД: {e}")
        return None

    if (url.drivername or "").split("+")[0] != "sqlite":
        logger.info(
            f"Бэкап: БД не sqlite (drivername={url.drivername}) — пропуск."
        )
        return None

    database = url.database
    if not database:
        return None

    # Абсолютный путь оставляем как есть; относительный — относительно
    # Flask instance_path (SQLAlchemy сам так разрешает sqlite:///foo.db).
    if os.path.isabs(database):
        return database
    return os.path.join(app.instance_path, database)


def schedule_daily_backups(app) -> None:
    """Запускает фоновый таймер: первый бэкап через несколько секунд,
    затем каждые BACKUP_INTERVAL_HOURS часов. Ротация — BACKUP_KEEP.
    """
    db_path = _resolve_db_path(app)
    if not db_path:
        return

    backup_dir = Settings.BACKUP_DIR
    keep = Settings.BACKUP_KEEP
    interval_seconds = max(1.0, Settings.BACKUP_INTERVAL_HOURS * 3600)
    first_delay = max(0.0, Settings.BACKUP_FIRST_DELAY_SECONDS)

    def _run():
        try:
            make_backup(db_path, backup_dir, keep)
        except Exception:
            logger.exception("Бэкап: ошибка при создании снапшота")
        # Перепланируем следующую попытку независимо от результата.
        t = threading.Timer(interval_seconds, _run)
        t.daemon = True
        t.start()

    t = threading.Timer(first_delay, _run)
    t.daemon = True
    t.start()
    logger.info(
        f"Планировщик бэкапов запущен: первая копия через "
        f"~{int(first_delay)} с, затем каждые "
        f"{Settings.BACKUP_INTERVAL_HOURS} ч, хранить {keep} копий "
        f"в {backup_dir}"
    )
