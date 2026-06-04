from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.entities import RuntimeTask
from app.models.schema_defs.phase4 import RuntimeTaskCreate
from app.services.runtime_worker_health import record_platform_component_heartbeat
from app.services.tasks import RuntimeTaskQueue
from app.services.tasks.queue import _recent_terminal_task_order


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


def test_runtime_task_queue_records_events_and_status(monkeypatch):
    db = _db()
    queue = RuntimeTaskQueue(db)
    published = []

    monkeypatch.setattr("app.services.tasks.queue.publish_runtime_task_event", lambda event: published.append(event.event_type))

    created = queue.enqueue(RuntimeTaskCreate(task_type="noop", payload={"ok": True}))
    claimed = queue.claim_next(worker_id="test-worker")
    assert claimed is not None
    assert claimed.id == created.id
    finished = queue.mark_succeeded(created.id, {"done": True})

    assert finished.status == "succeeded"
    events = queue.events(created.id)
    assert [event.event_type for event in events] == ["queued", "started", "succeeded"]
    assert published == ["queued", "started", "succeeded"]


def test_runtime_task_queue_recovers_stale_running_idempotent_task(monkeypatch):
    db = _db()
    queue = RuntimeTaskQueue(db)
    published = []

    monkeypatch.setattr("app.services.tasks.queue.publish_runtime_task_event", lambda event: published.append(event.event_type))

    created = queue.enqueue(
        RuntimeTaskCreate(
            task_type="monitor_snapshot_refresh",
            payload={"user_id": 3, "priority_limit": 12},
            idempotency_key="monitor_snapshot_refresh:3:12",
            max_attempts=2,
        )
    )
    row = db.get(RuntimeTask, created.id)
    assert row is not None
    row.status = "running"
    row.locked_by = "dead-worker"
    row.locked_at = datetime.utcnow() - timedelta(minutes=30)
    row.attempt_count = 1
    db.commit()

    enqueued = queue.enqueue(
        RuntimeTaskCreate(
            task_type="monitor_snapshot_refresh",
            payload={"user_id": 3, "priority_limit": 12},
            idempotency_key="monitor_snapshot_refresh:3:12",
            max_attempts=2,
        )
    )
    claimed = queue.claim_next(worker_id="new-worker")

    assert enqueued.id == created.id
    assert claimed is None
    db.refresh(row)
    assert row.status == "queued"
    assert row.locked_by == ""
    assert row.attempt_count == 1
    assert row.run_after is not None
    assert "retry" in published


def test_runtime_task_queue_retry_sets_future_run_after(monkeypatch):
    db = _db()
    queue = RuntimeTaskQueue(db)
    monkeypatch.setattr("app.services.tasks.queue.publish_runtime_task_event", lambda event: None)

    created = queue.enqueue(RuntimeTaskCreate(task_type="noop", payload={}, max_attempts=3))
    claimed = queue.claim_next(worker_id="test-worker")
    assert claimed is not None
    before_failure = datetime.utcnow()

    failed = queue.mark_failed(created.id, "provider unavailable", retryable=True)
    row = db.get(RuntimeTask, created.id)

    assert failed.status == "queued"
    assert row is not None
    assert row.run_after is not None
    assert row.run_after > before_failure
    assert queue.claim_next(worker_id="next-worker") is None


def test_runtime_task_queue_stale_recovery_requeues_with_backoff(monkeypatch):
    db = _db()
    queue = RuntimeTaskQueue(db)
    monkeypatch.setattr("app.services.tasks.queue.publish_runtime_task_event", lambda event: None)

    created = queue.enqueue(
        RuntimeTaskCreate(
            task_type="monitor_snapshot_refresh",
            payload={"user_id": 3, "priority_limit": 12},
            idempotency_key="monitor_snapshot_refresh:3:12",
            max_attempts=3,
        )
    )
    row = db.get(RuntimeTask, created.id)
    assert row is not None
    row.status = "running"
    row.locked_by = "dead-worker"
    row.locked_at = datetime.utcnow() - timedelta(minutes=30)
    row.attempt_count = 1
    db.commit()
    before_recovery = datetime.utcnow()

    queue.recover_stale_running_tasks()
    recovered = db.get(RuntimeTask, created.id)

    assert recovered is not None
    assert recovered.status == "queued"
    assert recovered.run_after is not None
    assert recovered.run_after > before_recovery
    assert queue.claim_next(worker_id="new-worker") is None


def test_runtime_task_summary_is_read_only_for_stale_running_tasks(monkeypatch):
    db = _db()
    queue = RuntimeTaskQueue(db)
    monkeypatch.setattr("app.services.tasks.queue.publish_runtime_task_event", lambda event: None)

    created = queue.enqueue(RuntimeTaskCreate(task_type="monitor_snapshot_refresh", payload={}, max_attempts=2))
    row = db.get(RuntimeTask, created.id)
    assert row is not None
    row.status = "running"
    row.locked_by = "dead-worker"
    row.locked_at = datetime.utcnow() - timedelta(minutes=30)
    row.attempt_count = 1
    db.commit()

    summary = queue.summary()
    db.refresh(row)

    assert summary.running == 1
    assert row.status == "running"
    assert row.locked_by == "dead-worker"
    assert row.run_after is None


def test_runtime_task_queue_observability_summary_workers_failures_and_artifacts(monkeypatch):
    db = _db()
    queue = RuntimeTaskQueue(db)
    monkeypatch.setattr("app.services.tasks.queue.publish_runtime_task_event", lambda event: None)
    record_platform_component_heartbeat(
        db,
        component="runtime-worker",
        worker_id="runtime-test",
        now=datetime.utcnow(),
    )
    for component in ("runtime-scheduler", "analytics-worker", "backtest-worker"):
        record_platform_component_heartbeat(
            db,
            component=component,
            worker_id=component,
            now=datetime.utcnow(),
        )
    db.commit()

    queued = queue.enqueue(RuntimeTaskCreate(task_type="data_quality_backfill", payload={"output_path": "/tmp/input.json"}))
    running = queue.enqueue(RuntimeTaskCreate(task_type="strategy_24m_duckdb_report", payload={}))
    failed = queue.enqueue(RuntimeTaskCreate(task_type="analytics_quality_check", payload={}))
    succeeded = queue.enqueue(RuntimeTaskCreate(task_type="analytics_export_daily_bars", payload={}))
    assert queue.claim_next(worker_id="runtime-test") is not None
    db.get(RuntimeTask, running.id).status = "running"
    db.get(RuntimeTask, running.id).locked_by = "runtime-test"
    db.get(RuntimeTask, failed.id).status = "failed"
    db.get(RuntimeTask, failed.id).error_message = "provider unavailable"
    db.get(RuntimeTask, succeeded.id).status = "succeeded"
    db.get(RuntimeTask, succeeded.id).result_json = '{"output_json":"/tmp/report.json","manifest_path":"/tmp/manifest.json"}'
    db.add(RuntimeTask(task_type="data_quality_sla_refresh", status="queued", priority=40, payload_json="{}"))
    db.commit()

    summary = queue.summary()
    workers = queue.workers()
    failures = queue.failures()
    artifacts = queue.artifacts()

    assert summary.queued >= 1
    assert summary.running >= 1
    assert summary.failed >= 1
    assert any(item.task_type == "analytics_export_daily_bars" for item in summary.task_type_counts)
    components = {item.component for item in workers.items}
    assert components >= {"runtime-worker", "runtime-scheduler", "analytics-worker", "backtest-worker"}
    runtime_worker = next(item for item in workers.items if item.component == "runtime-worker")
    assert runtime_worker.worker_id == "runtime-test"
    assert runtime_worker.running_task_count >= 1
    assert failures.items[0].error_message == "provider unavailable"
    assert {item.artifact_path for item in artifacts.items} >= {"/tmp/report.json", "/tmp/manifest.json"}


def test_runtime_task_recent_terminal_order_compiles_for_mysql_without_nulls_last():
    statement = (
        select(RuntimeTask)
        .where(RuntimeTask.status == "failed")
        .order_by(*_recent_terminal_task_order())
        .limit(20)
    )

    compiled = str(statement.compile(dialect=mysql.dialect()))

    assert "NULLS LAST" not in compiled
    assert "finished_at IS NULL" in compiled
