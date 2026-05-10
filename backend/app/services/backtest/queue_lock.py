from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import text
from sqlalchemy.orm import Session


@contextmanager
def backtest_claim_lock(db: Session, *, lock_name: str = "tquant_backtest_claim", timeout_seconds: int = 2):
    """Serialize queue claims across MySQL workers; no-op for local SQLite."""

    dialect = db.get_bind().dialect.name
    if dialect != "mysql":
        yield
        return

    acquired = db.execute(text("SELECT GET_LOCK(:name, :timeout)"), {"name": lock_name, "timeout": timeout_seconds}).scalar()
    if acquired != 1:
        yield False
        return
    try:
        yield True
    finally:
        db.execute(text("SELECT RELEASE_LOCK(:name)"), {"name": lock_name})
