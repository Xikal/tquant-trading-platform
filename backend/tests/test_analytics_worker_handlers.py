from __future__ import annotations

from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.services.tasks.worker as worker_module
from app.models.base import Base
from app.models.schema_defs.phase4 import RuntimeTaskCreate
from app.services.analytics.exporters import export_daily_bars_parquet
from app.services.tasks import RuntimeTaskQueue
from app.services.tasks.analytics_handlers import register_analytics_handlers
from app.services.tasks.registry import TaskHandlerRegistry
from app.services.tasks.worker import RuntimeTaskWorker


def _db_factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def test_analytics_quality_check_consumes_manifest_with_explicit_status(monkeypatch, tmp_path) -> None:
    session_factory = _db_factory()
    monkeypatch.setattr(worker_module, "SessionLocal", session_factory)
    with session_factory() as db:
        manifest = export_daily_bars_parquet(
            db,
            months=24,
            end_date=date(2026, 6, 4),
            output_root=tmp_path,
            create_backfill_task=False,
        )
        task = RuntimeTaskQueue(db).enqueue(
            RuntimeTaskCreate(
                task_type="analytics_quality_check",
                payload={"manifest": manifest["manifest_path"], "output_root": str(tmp_path)},
                max_attempts=1,
            )
        )

    registry = TaskHandlerRegistry()
    register_analytics_handlers(registry)
    worker = RuntimeTaskWorker(registry=registry, worker_id="analytics-b2", poll_interval_seconds=0.1)

    assert worker.run_once() is True

    with session_factory() as db:
        finished = RuntimeTaskQueue(db).get(task.id)
    assert finished.status == "succeeded"
    assert finished.result["ok"] is False
    assert finished.result["status"] == "no_data"
    assert finished.result["manifest"]["dataset"] == "daily_bars"


def test_strategy_report_worker_records_blocked_artifacts_instead_of_retrying(monkeypatch, tmp_path) -> None:
    session_factory = _db_factory()
    monkeypatch.setattr(worker_module, "SessionLocal", session_factory)
    output_md = tmp_path / "reports" / "strategy.md"
    output_json = tmp_path / "reports" / "strategy.json"
    with session_factory() as db:
        manifest = export_daily_bars_parquet(
            db,
            months=24,
            end_date=date(2026, 6, 4),
            output_root=tmp_path,
            create_backfill_task=False,
        )
        task = RuntimeTaskQueue(db).enqueue(
            RuntimeTaskCreate(
                task_type="strategy_24m_duckdb_report",
                payload={
                    "manifest": manifest["manifest_path"],
                    "output_root": str(tmp_path),
                    "output_md": str(output_md),
                    "output_json": str(output_json),
                },
                max_attempts=1,
            )
        )

    registry = TaskHandlerRegistry()
    register_analytics_handlers(registry)
    worker = RuntimeTaskWorker(registry=registry, worker_id="analytics-b2", poll_interval_seconds=0.1)

    assert worker.run_once() is True

    with session_factory() as db:
        finished = RuntimeTaskQueue(db).get(task.id)
    assert finished.status == "succeeded"
    assert finished.result["ok"] is False
    assert finished.result["status"] == "blocked_by_data"
    assert str(output_md) in finished.result["artifacts"]
    assert str(output_json) in finished.result["artifacts"]
    assert output_md.exists()
    assert output_json.exists()
