from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.entities import RuntimeTask, RuntimeTaskEvent
from app.models.schema_defs.phase4 import RuntimeTaskCreate, RuntimeTaskEventOut, RuntimeTaskListResponse, RuntimeTaskOut
from app.services.realtime import publish_runtime_task_event


TERMINAL_STATUSES = {"succeeded", "failed", "cancelled"}
RUNNING_TASK_STALE_SECONDS = 5 * 60
STALE_RECOVERY_BATCH_SIZE = 20
RETRY_BACKOFF_BASE_SECONDS = 30
RETRY_BACKOFF_MAX_SECONDS = 15 * 60


class RuntimeTaskQueue:
    """Small DB-backed task queue.

    This is intentionally simple so cloud deployment does not need Redis on day
    one. It gives us durable status, retries, and an event stream. Celery/RQ can
    replace the adapter later without changing public API contracts.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def enqueue(self, payload: RuntimeTaskCreate) -> RuntimeTaskOut:
        self._recover_stale_running_tasks()
        active_key = str(payload.idempotency_key or "").strip() or None
        if active_key:
            existing = self._find_active_idempotent_task(active_key)
            if existing is not None:
                return _task_out(existing)
        row = RuntimeTask(
            task_type=payload.task_type,
            payload_json=_json_dumps(payload.payload),
            priority=payload.priority,
            idempotency_key=payload.idempotency_key,
            active_idempotency_key=active_key,
            max_attempts=payload.max_attempts,
        )
        self.db.add(row)
        try:
            self.db.flush()
        except IntegrityError:
            self.db.rollback()
            if active_key:
                existing = self._find_active_idempotent_task(active_key)
                if existing is not None:
                    return _task_out(existing)
            raise
        event = self.add_event(row.id, "queued", "任务已入队", {"task_type": row.task_type})
        self.db.commit()
        publish_runtime_task_event(event)
        self.db.refresh(row)
        return _task_out(row)

    def list(self, *, limit: int = 50, offset: int = 0, status: str | None = None) -> RuntimeTaskListResponse:
        statement = select(RuntimeTask)
        count_statement = select(func.count(RuntimeTask.id))
        if status:
            statement = statement.where(RuntimeTask.status == status)
            count_statement = count_statement.where(RuntimeTask.status == status)
        rows = self.db.execute(
            statement.order_by(RuntimeTask.id.desc()).offset(offset).limit(limit)
        ).scalars().all()
        total = int(self.db.execute(count_statement).scalar() or 0)
        return RuntimeTaskListResponse(items=[_task_out(row) for row in rows], total=total, limit=limit, offset=offset)

    def get(self, task_id: int) -> RuntimeTaskOut:
        row = self._get_row(task_id)
        return _task_out(row)

    def recover_stale_running_tasks(self) -> None:
        self._recover_stale_running_tasks()

    def events(self, task_id: int, *, after_id: int = 0, limit: int = 100) -> list[RuntimeTaskEventOut]:
        rows = self.db.execute(
            select(RuntimeTaskEvent)
            .where(RuntimeTaskEvent.task_id == task_id)
            .where(RuntimeTaskEvent.id > after_id)
            .order_by(RuntimeTaskEvent.id.asc())
            .limit(limit)
        ).scalars().all()
        return [_event_out(row) for row in rows]

    def claim_next(self, *, worker_id: str, task_types: list[str] | tuple[str, ...] | None = None) -> RuntimeTask | None:
        self._recover_stale_running_tasks()
        statement = (
            select(RuntimeTask)
            .where(RuntimeTask.status == "queued")
            .where(or_(RuntimeTask.run_after.is_(None), RuntimeTask.run_after <= datetime.utcnow()))
            .order_by(RuntimeTask.priority.asc(), RuntimeTask.id.asc())
            .limit(1)
        )
        if task_types:
            statement = statement.where(RuntimeTask.task_type.in_([str(item) for item in task_types]))
        if _supports_skip_locked(self.db):
            statement = statement.with_for_update(skip_locked=True)
        row = self.db.execute(statement).scalar_one_or_none()
        if row is None:
            return None
        row.status = "running"
        row.locked_by = worker_id
        row.locked_at = datetime.utcnow()
        row.started_at = row.started_at or row.locked_at
        row.attempt_count = int(row.attempt_count or 0) + 1
        event = self.add_event(row.id, "started", "任务开始执行", {"worker_id": worker_id})
        self.db.commit()
        publish_runtime_task_event(event)
        self.db.refresh(row)
        return row

    def heartbeat(self, task_id: int, *, worker_id: str = "") -> RuntimeTaskOut:
        row = self._get_row(task_id)
        row.locked_at = datetime.utcnow()
        if worker_id:
            row.locked_by = worker_id
        self.db.commit()
        self.db.refresh(row)
        return _task_out(row)

    def update_progress(
        self,
        task_id: int,
        *,
        progress_pct: float,
        message: str = "",
        payload: dict[str, Any] | None = None,
    ) -> RuntimeTaskOut:
        row = self._get_row(task_id)
        row.progress_pct = max(0.0, min(float(progress_pct), 99.0))
        row.locked_at = datetime.utcnow()
        event = self.add_event(task_id, "progress", message or "任务进度更新", payload or {})
        self.db.commit()
        publish_runtime_task_event(event)
        self.db.refresh(row)
        return _task_out(row)

    def mark_succeeded(self, task_id: int, result: dict[str, Any] | None = None) -> RuntimeTaskOut:
        row = self._get_row(task_id)
        row.status = "succeeded"
        row.active_idempotency_key = None
        row.result_json = _json_dumps(result or {})
        row.progress_pct = 100.0
        row.finished_at = datetime.utcnow()
        event = self.add_event(task_id, "succeeded", "任务执行完成", result or {})
        self.db.commit()
        publish_runtime_task_event(event)
        self.db.refresh(row)
        return _task_out(row)

    def mark_failed(self, task_id: int, message: str, *, retryable: bool = True) -> RuntimeTaskOut:
        row = self._get_row(task_id)
        should_retry = retryable and int(row.attempt_count or 0) < int(row.max_attempts or 1)
        row.status = "queued" if should_retry else "failed"
        row.error_message = message[:1000]
        if should_retry:
            row.locked_by = ""
            row.locked_at = None
            row.run_after = _next_retry_at(row.attempt_count)
        else:
            row.run_after = None
            row.active_idempotency_key = None
            row.finished_at = datetime.utcnow()
        event = self.add_event(task_id, "retry" if should_retry else "failed", message[:240])
        self.db.commit()
        publish_runtime_task_event(event)
        self.db.refresh(row)
        return _task_out(row)

    def add_event(
        self,
        task_id: int,
        event_type: str,
        message: str = "",
        payload: dict[str, Any] | None = None,
    ) -> RuntimeTaskEventOut:
        row = RuntimeTaskEvent(
            task_id=task_id,
            event_type=event_type,
            message=message,
            payload_json=_json_dumps(payload or {}),
        )
        self.db.add(row)
        self.db.flush()
        return _event_out(row)

    def _get_row(self, task_id: int) -> RuntimeTask:
        row = self.db.get(RuntimeTask, task_id)
        if row is None:
            raise LookupError("后台任务不存在")
        return row

    def _find_active_idempotent_task(self, active_key: str) -> RuntimeTask | None:
        return self.db.execute(
            select(RuntimeTask)
            .where(RuntimeTask.active_idempotency_key == active_key)
            .where(~RuntimeTask.status.in_(TERMINAL_STATUSES))
            .order_by(RuntimeTask.id.desc())
            .limit(1)
        ).scalar_one_or_none()

    def _recover_stale_running_tasks(self) -> None:
        """Requeue tasks abandoned by a crashed worker.

        Monitor snapshots and other runtime jobs are idempotent. If a worker is
        killed while a task is running, leaving the row in ``running`` would make
        future idempotent enqueue calls return that stale row forever and the UI
        would keep receiving pending/empty snapshots. Recovery is deliberately
        bounded per queue touch so normal hot paths do not scan the full table.
        """

        cutoff = datetime.utcnow() - timedelta(seconds=RUNNING_TASK_STALE_SECONDS)
        rows = self.db.execute(
            select(RuntimeTask)
            .where(RuntimeTask.status == "running")
            .where(
                or_(
                    RuntimeTask.locked_at <= cutoff,
                    and_(RuntimeTask.locked_at.is_(None), RuntimeTask.updated_at <= cutoff),
                )
            )
            .order_by(RuntimeTask.id.asc())
            .limit(STALE_RECOVERY_BATCH_SIZE)
        ).scalars().all()
        if not rows:
            return

        events: list[RuntimeTaskEventOut] = []
        now = datetime.utcnow()
        for row in rows:
            row.locked_by = ""
            row.locked_at = None
            row.error_message = "任务运行超时，已自动恢复。"
            if int(row.attempt_count or 0) >= int(row.max_attempts or 1):
                row.status = "failed"
                row.active_idempotency_key = None
                row.finished_at = now
                events.append(self.add_event(row.id, "failed", "任务运行超时，已标记失败"))
            else:
                row.status = "queued"
                row.run_after = _next_retry_at(row.attempt_count)
                events.append(self.add_event(row.id, "retry", "任务运行超时，已重新排队"))
        self.db.commit()
        for event in events:
            publish_runtime_task_event(event)


def _task_out(row: RuntimeTask) -> RuntimeTaskOut:
    return RuntimeTaskOut(
        id=row.id,
        task_type=row.task_type,
        status=row.status,
        priority=row.priority,
        payload=_json_dict(row.payload_json),
        result=_json_dict(row.result_json),
        error_message=row.error_message,
        attempt_count=row.attempt_count,
        max_attempts=row.max_attempts,
        progress_pct=row.progress_pct,
        locked_by=row.locked_by,
        created_at=row.created_at,
        updated_at=row.updated_at,
        started_at=row.started_at,
        finished_at=row.finished_at,
    )


def _supports_skip_locked(db: Session) -> bool:
    bind = db.get_bind()
    dialect = getattr(bind, "dialect", None)
    name = getattr(dialect, "name", "")
    return name in {"mysql", "postgresql"}


def _next_retry_at(attempt_count: int | None) -> datetime:
    attempt = max(1, int(attempt_count or 1))
    seconds = min(RETRY_BACKOFF_MAX_SECONDS, RETRY_BACKOFF_BASE_SECONDS * (2 ** (attempt - 1)))
    return datetime.utcnow() + timedelta(seconds=seconds)


def _event_out(row: RuntimeTaskEvent) -> RuntimeTaskEventOut:
    return RuntimeTaskEventOut(
        id=row.id,
        task_id=row.task_id,
        event_type=row.event_type,
        message=row.message,
        payload=_json_dict(row.payload_json),
        created_at=row.created_at,
    )


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _json_dict(raw: str) -> dict[str, Any]:
    try:
        value = json.loads(raw or "{}")
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}
