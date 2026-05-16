from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import AppSettings
from app.models.base import Base
from app.models.entities import RuntimeTask
from app.runtime.strategy_evolution_scheduler import enqueue_daily_ledger_reconcile_preview_once


def _db_session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def test_enqueue_daily_ledger_reconcile_preview_uses_configured_schedule(monkeypatch) -> None:
    session_factory = _db_session_factory()
    settings = AppSettings(
        evolution_ledger_scheduler_hour=19,
        evolution_ledger_due_minute=0,
        evolution_ledger_gap_alert_threshold=2.5,
    )
    monkeypatch.setattr("app.runtime.strategy_evolution_scheduler.get_settings", lambda: settings)
    monkeypatch.setattr("app.runtime.strategy_evolution_scheduler.SessionLocal", session_factory)

    task = enqueue_daily_ledger_reconcile_preview_once(datetime(2026, 5, 18, 19, 5))

    with session_factory() as db:
        rows = db.query(RuntimeTask).all()
        assert len(rows) == 1
        assert rows[0].task_type == "paper_ledger_reconcile_preview"
        assert '"threshold": 2.5' in rows[0].payload_json
    assert task is not None
    assert task.task_type == "paper_ledger_reconcile_preview"


def test_enqueue_daily_ledger_reconcile_preview_skips_before_due_time(monkeypatch) -> None:
    session_factory = _db_session_factory()
    settings = AppSettings(evolution_ledger_scheduler_hour=19, evolution_ledger_due_minute=0)
    monkeypatch.setattr("app.runtime.strategy_evolution_scheduler.get_settings", lambda: settings)
    monkeypatch.setattr("app.runtime.strategy_evolution_scheduler.SessionLocal", session_factory)

    task = enqueue_daily_ledger_reconcile_preview_once(datetime(2026, 5, 18, 18, 59))

    with session_factory() as db:
        assert db.query(RuntimeTask).count() == 0
    assert task is None
