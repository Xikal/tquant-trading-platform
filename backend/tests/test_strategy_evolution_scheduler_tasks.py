from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.entities import RuntimeTask
from app.runtime.strategy_evolution_scheduler import enqueue_strategy_self_evolution_once


def _db_session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def test_strategy_self_evolution_scheduler_skips_removed_paper_sample_source(monkeypatch) -> None:
    session_factory = _db_session_factory()
    monkeypatch.setattr("app.runtime.strategy_evolution_scheduler.SessionLocal", session_factory)

    task = enqueue_strategy_self_evolution_once(datetime(2026, 5, 22, 19, 5))

    with session_factory() as db:
        assert db.query(RuntimeTask).count() == 0
    assert task is None
