from __future__ import annotations

from pathlib import Path
from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.entities import DailyBarSnapshot
from app.models.schema_defs.phase4 import RuntimeTaskCreate
from app.services.tasks import RuntimeTaskQueue
from app.services.tasks.analytics_handlers import register_analytics_handlers
from app.services.tasks.registry import TaskHandlerRegistry
from app.services.tasks.worker import RuntimeTaskWorker
import app.services.tasks.worker as worker_module


def _db_factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def test_worker_runs_registered_handler_with_progress_and_artifact(monkeypatch, tmp_path):
    session_factory = _db_factory()
    monkeypatch.setattr(worker_module, "SessionLocal", session_factory)
    artifact = tmp_path / "report.json"

    registry = TaskHandlerRegistry()

    def handler(context):
        artifact.write_text("{}", encoding="utf-8")
        context.progress(50, "half")
        context.add_artifact(str(artifact))
        return {"ok": True}

    registry.register("strategy_24m_duckdb_report", handler)
    with session_factory() as db:
        task = RuntimeTaskQueue(db).enqueue(
            RuntimeTaskCreate(task_type="strategy_24m_duckdb_report", payload={"months": 24})
        )

    worker = RuntimeTaskWorker(registry=registry, worker_id="test-analytics", poll_interval_seconds=0.1)
    assert worker.run_once() is True

    with session_factory() as db:
        finished = RuntimeTaskQueue(db).get(task.id)
        events = RuntimeTaskQueue(db).events(task.id)
    assert finished.status == "succeeded"
    assert finished.progress_pct == 100
    assert str(artifact) in finished.result["artifacts"]
    assert "progress" in [item.event_type for item in events]
    assert "artifact" in [item.event_type for item in events]


def test_analytics_registry_exposes_decision_context_report_aliases():
    registry = TaskHandlerRegistry()
    register_analytics_handlers(registry)

    task_types = set(registry.task_types())
    assert "decision_context_24m_report" in task_types
    assert "portfolio_execution_24m_report" in task_types


def test_analytics_registry_exposes_data_quality_tasks():
    registry = TaskHandlerRegistry()
    register_analytics_handlers(registry)

    task_types = set(registry.task_types())
    assert "data_quality_sla_refresh" in task_types
    assert "data_repair_run" in task_types


def test_worker_consumes_data_quality_sla_refresh(monkeypatch):
    session_factory = _db_factory()
    monkeypatch.setattr(worker_module, "SessionLocal", session_factory)
    with session_factory() as db:
        db.add(
            DailyBarSnapshot(
                symbol="600000",
                market="CN",
                instrument_type="stock",
                trade_date=date(2026, 5, 29),
                open_price=10,
                close_price=10.2,
                high_price=10.5,
                low_price=9.8,
                volume=1000,
                amount=10000,
                source="unit-test",
                data_quality="ok",
            )
        )
        db.commit()
        task = RuntimeTaskQueue(db).enqueue(
            RuntimeTaskCreate(
                task_type="data_quality_sla_refresh",
                payload={
                    "datasets": ["daily_bars"],
                    "scope": "production_universe",
                    "start_date": "2026-05-29",
                    "end_date": "2026-05-29",
                    "expected_days": 1,
                },
                max_attempts=1,
            )
        )

    registry = TaskHandlerRegistry()
    register_analytics_handlers(registry)
    worker = RuntimeTaskWorker(registry=registry, worker_id="test-analytics", poll_interval_seconds=0.1)

    assert worker.run_once() is True

    with session_factory() as db:
        finished = RuntimeTaskQueue(db).get(task.id)
    assert finished.status == "succeeded"
    assert finished.result["data_quality_sla"]["items"][0]["status"] == "ok"


def test_worker_consumes_data_repair_run_dry_run(monkeypatch, tmp_path):
    session_factory = _db_factory()
    monkeypatch.setattr(worker_module, "SessionLocal", session_factory)
    output = tmp_path / "repair.json"
    with session_factory() as db:
        db.add(
            DailyBarSnapshot(
                symbol="600000",
                market="CN",
                instrument_type="stock",
                trade_date=date(2026, 5, 29),
                open_price=0,
                close_price=10.2,
                high_price=10.5,
                low_price=9.8,
                volume=1000,
                amount=10000,
                source="unit-test",
                data_quality="ok",
            )
        )
        db.commit()
        task = RuntimeTaskQueue(db).enqueue(
            RuntimeTaskCreate(
                task_type="data_repair_run",
                payload={"dataset_key": "daily_bars", "dry_run": True, "output_path": str(output)},
                max_attempts=1,
            )
        )

    registry = TaskHandlerRegistry()
    register_analytics_handlers(registry)
    worker = RuntimeTaskWorker(registry=registry, worker_id="test-analytics", poll_interval_seconds=0.1)

    assert worker.run_once() is True

    with session_factory() as db:
        finished = RuntimeTaskQueue(db).get(task.id)
    assert finished.status == "succeeded"
    assert finished.result["repair"]["matched_rows"] == 1
    assert output.exists()
