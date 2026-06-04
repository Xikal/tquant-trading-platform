from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.services.tasks.worker as worker_module
from app.models.base import Base
from app.models.entities import RuntimeTask
from app.models.schema_defs.phase4 import RuntimeTaskCreate
from app.services.tasks import RuntimeTaskQueue
from app.services.tasks.analytics_handlers import register_analytics_handlers
from app.services.tasks.registry import TaskHandlerRegistry, analytics_task_registry
from app.services.tasks.worker import RuntimeTaskWorker


def _db_factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def test_phase3_analytics_registry_exposes_required_long_tasks() -> None:
    task_types = set(analytics_task_registry().task_types())

    assert {
        "data_backfill_24m",
        "analytics_export_daily_bars",
        "analytics_quality_check",
        "strategy_24m_duckdb_report",
        "backtest_all_strategies_24m",
    }.issubset(task_types)


def test_runtime_task_worker_persists_heartbeat_progress_and_artifact(monkeypatch, tmp_path: Path) -> None:
    session_factory = _db_factory()
    monkeypatch.setattr(worker_module, "SessionLocal", session_factory)
    artifact = tmp_path / "phase3-artifact.json"
    registry = TaskHandlerRegistry()

    def handler(context):
        context.heartbeat()
        context.progress(45, "phase3 progress")
        artifact.write_text("{}", encoding="utf-8")
        context.add_artifact(str(artifact))
        return {"ok": True}

    registry.register("phase3_probe", handler)
    with session_factory() as db:
        task = RuntimeTaskQueue(db).enqueue(RuntimeTaskCreate(task_type="phase3_probe", payload={}))

    worker = RuntimeTaskWorker(registry=registry, worker_id="phase3-worker", poll_interval_seconds=0.1)

    assert worker.run_once() is True

    with session_factory() as db:
        finished = RuntimeTaskQueue(db).get(task.id)
        row = db.get(RuntimeTask, task.id)
        events = RuntimeTaskQueue(db).events(task.id)
    assert row is not None
    assert row.locked_by == "phase3-worker"
    assert finished.status == "succeeded"
    assert finished.progress_pct == 100
    assert str(artifact) in finished.result["artifacts"]
    assert {"queued", "started", "progress", "artifact", "succeeded"}.issubset(
        {event.event_type for event in events}
    )


def test_runtime_task_worker_failure_retries_with_failure_event(monkeypatch) -> None:
    session_factory = _db_factory()
    monkeypatch.setattr(worker_module, "SessionLocal", session_factory)
    registry = TaskHandlerRegistry()

    def handler(_context):
        raise RuntimeError("transient worker failure")

    registry.register("phase3_retry_probe", handler)
    with session_factory() as db:
        task = RuntimeTaskQueue(db).enqueue(
            RuntimeTaskCreate(task_type="phase3_retry_probe", payload={}, max_attempts=2)
        )

    worker = RuntimeTaskWorker(registry=registry, worker_id="phase3-worker", poll_interval_seconds=0.1)

    assert worker.run_once() is True

    with session_factory() as db:
        retried = RuntimeTaskQueue(db).get(task.id)
        row = db.get(RuntimeTask, task.id)
        events = RuntimeTaskQueue(db).events(task.id)
    assert row is not None
    assert retried.status == "queued"
    assert row.run_after is not None
    assert row.error_message == "transient worker failure"
    assert "retry" in {event.event_type for event in events}


def test_analytics_worker_runs_quality_check_and_enqueues_backfill_when_data_missing(monkeypatch) -> None:
    session_factory = _db_factory()
    monkeypatch.setattr(worker_module, "SessionLocal", session_factory)
    with session_factory() as db:
        task = RuntimeTaskQueue(db).enqueue(
            RuntimeTaskCreate(
                task_type="analytics_quality_check",
                payload={"months": 24, "end_date": "2026-06-04"},
                max_attempts=1,
            )
        )

    registry = TaskHandlerRegistry()
    register_analytics_handlers(registry)
    worker = RuntimeTaskWorker(registry=registry, worker_id="analytics-phase3", poll_interval_seconds=0.1)

    assert worker.run_once() is True

    with session_factory() as db:
        finished = RuntimeTaskQueue(db).get(task.id)
        rows = db.execute(select(RuntimeTask).order_by(RuntimeTask.id.asc())).scalars().all()
    assert finished.status == "succeeded"
    assert finished.result["ok"] is False
    assert finished.result["quality"]["status"] == "fail"
    assert "daily_bars_empty" in finished.result["quality"]["blockers"]
    assert any(row.task_type == "data_backfill_24m" and row.status == "queued" for row in rows)
