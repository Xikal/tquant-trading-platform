from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.entities import BacktestRun
from app.services.backtest_queue_metrics import backtest_queue_snapshot


def _session_factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def test_backtest_queue_estimate_uses_recent_tier_average() -> None:
    SessionLocal = _session_factory()
    now = datetime.utcnow()
    with SessionLocal() as db:
        db.add(
            BacktestRun(
                name="recent-walk-forward",
                status="succeeded",
                params_json='{"resource_tier": "walk_forward"}',
                started_at=now - timedelta(seconds=240),
                finished_at=now,
                initial_cash=100000.0,
                final_equity=101000.0,
            )
        )
        first = _queued_run("queued-one", "walk_forward")
        second = _queued_run("queued-two", "light")
        db.add_all([first, second])
        db.commit()
        db.refresh(second)

        snapshot = backtest_queue_snapshot(db, second)

    assert snapshot.estimated_wait_seconds >= 120
    assert snapshot.estimated_wait_reliable is True
    assert snapshot.estimated_wait_source == "historical_tier_average"


def test_backtest_queue_estimate_ignores_expired_history(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.backtest_queue_metrics.get_backtest_execution",
        lambda: {
            "max_concurrent_backtests": 1,
            "queue_estimate_sample_size": 3,
            "queue_estimate_max_age_days": 1,
        },
    )
    SessionLocal = _session_factory()
    now = datetime.utcnow()
    with SessionLocal() as db:
        db.add(
            BacktestRun(
                name="expired-walk-forward",
                status="succeeded",
                params_json='{"resource_tier": "walk_forward"}',
                started_at=now - timedelta(days=10, seconds=240),
                finished_at=now - timedelta(days=10),
                initial_cash=100000.0,
                final_equity=101000.0,
            )
        )
        first = _queued_run("queued-one", "walk_forward")
        second = _queued_run("queued-two", "light")
        db.add_all([first, second])
        db.commit()
        db.refresh(second)

        snapshot = backtest_queue_snapshot(db, second)

    assert snapshot.estimated_wait_seconds == 180
    assert snapshot.estimated_wait_reliable is False
    assert snapshot.estimated_wait_source == "fallback_resource_tier"


def _queued_run(name: str, tier: str) -> BacktestRun:
    return BacktestRun(
        name=name,
        status="queued",
        params_json=f'{{"resource_tier": "{tier}"}}',
        initial_cash=100000.0,
        final_equity=100000.0,
    )
