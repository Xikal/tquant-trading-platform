from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.entities import RuntimeTask
from app.models.schema_defs.phase4 import RuntimeTaskCreate
from app.services.tasks import RuntimeTaskQueue


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
