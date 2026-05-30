from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
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
