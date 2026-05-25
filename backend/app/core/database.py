from __future__ import annotations

import logging
from pathlib import Path
from shutil import copy2

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.schema_compat import ensure_schema_compatibility, verify_schema_compatibility
from app.models.base import Base

logger = logging.getLogger(__name__)


def _sqlite_connect_args(database_url: str) -> dict:
    return {"check_same_thread": False} if database_url.startswith("sqlite") else {}


def _sqlite_database_path(database_url: str) -> Path | None:
    if not database_url.startswith("sqlite:///"):
        return None
    raw_path = database_url.replace("sqlite:///", "", 1)
    return Path(raw_path)


def _ensure_sqlite_storage(database_url: str) -> None:
    database_path = _sqlite_database_path(database_url)
    if database_path is None:
        return

    database_path.parent.mkdir(parents=True, exist_ok=True)

    if database_path.exists():
        return

    seed_path = Path(__file__).resolve().parents[2] / "data" / "t_quant.db"
    if not seed_path.exists():
        return

    try:
        if database_path.resolve() == seed_path.resolve():
            return
    except FileNotFoundError:
        pass

    copy2(seed_path, database_path)


settings = get_settings()
_ensure_sqlite_storage(settings.database_url)

_engine_kwargs = dict(
    future=True,
    pool_pre_ping=True,
    connect_args=_sqlite_connect_args(settings.database_url),
)
if settings.database_url.startswith("mysql"):
    _engine_kwargs.update(
        pool_size=max(int(settings.db_pool_size or 12), 1),
        max_overflow=max(int(settings.db_max_overflow or 24), 0),
        pool_timeout=max(int(settings.db_pool_timeout or 30), 1),
        pool_recycle=max(int(settings.db_pool_recycle or 1800), 60),
    )

engine = create_engine(
    settings.database_url,
    **_engine_kwargs,
)


def _configure_sqlite_connection(dbapi_connection, _connection_record) -> None:
    """Enable pragmatic SQLite settings for web/API concurrent reads.

    SQLite remains a single-writer database, but WAL and a busy timeout reduce
    avoidable `database is locked` failures when background jobs and API reads
    overlap.
    """

    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
    except Exception:
        logger.exception("failed to apply SQLite connection pragmas")
    finally:
        cursor.close()


if settings.database_url.startswith("sqlite"):
    event.listen(engine, "connect", _configure_sqlite_connection)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    if settings.database_url.startswith("sqlite") or settings.schema_compat_repair_enabled:
        Base.metadata.create_all(bind=engine)
    if settings.schema_compat_repair_enabled or _sqlite_dev_repair_enabled():
        ensure_schema_compatibility(engine)
        return
    if settings.schema_compat_verify_on_startup:
        verify_schema_compatibility(engine)


def ping_database() -> None:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))


def _sqlite_dev_repair_enabled() -> bool:
    if not settings.database_url.startswith("sqlite"):
        return False
    return settings.app_environment.strip().lower() not in {"prod", "production", "cloud"}
