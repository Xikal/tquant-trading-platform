from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.entities import RuntimeTask, SystemSetting
from app.services.runtime_worker_health import build_runtime_fallback_status, record_runtime_worker_heartbeat


def test_runtime_fallback_status_blocks_when_worker_heartbeat_missing():
    db = _db()

    status = build_runtime_fallback_status(db, now=datetime(2026, 6, 3, 16, 0, 0))

    assert status["worker_status"] == "missing"
    assert status["blocking"] is True
    assert "runtime worker" in status["message"].lower()


def test_runtime_fallback_status_blocks_when_critical_task_stuck():
    db = _db()
    db.add(
        SystemSetting(
            key="runtime_worker.heartbeat",
            value='{"worker_id":"runtime-test","updated_at":"2026-06-03T15:59:30","status":"running"}',
        )
    )
    db.add(
        RuntimeTask(
            task_type="low_buy_materialization_refresh",
            status="queued",
            priority=35,
            payload_json='{"expected_trade_date":"2026-06-03"}',
            idempotency_key="low_buy_materialization_refresh:2026-06-03",
            active_idempotency_key="low_buy_materialization_refresh:2026-06-03",
            created_at=datetime(2026, 6, 3, 15, 45, 0),
        )
    )
    db.commit()

    status = build_runtime_fallback_status(db, now=datetime(2026, 6, 3, 16, 0, 0))

    assert status["worker_status"] == "running"
    assert status["blocking"] is True
    assert status["critical_queued_count"] == 1
    assert status["oldest_critical_queued_age_seconds"] >= 900


def test_record_runtime_worker_heartbeat_updates_setting():
    db = _db()

    record_runtime_worker_heartbeat(
        db,
        worker_id="runtime-test",
        now=datetime(2026, 6, 3, 16, 0, 0),
    )

    status = build_runtime_fallback_status(db, now=datetime(2026, 6, 3, 16, 0, 10))

    assert status["worker_status"] == "running"
    assert status["worker_id"] == "runtime-test"
    assert status["blocking"] is False


def _db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return session_factory()
