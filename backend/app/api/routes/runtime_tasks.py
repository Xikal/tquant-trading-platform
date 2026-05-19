from __future__ import annotations

import json
import time

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.admin_auth import require_admin_auth
from app.core.config import get_settings
from app.core.database import SessionLocal, get_db
from app.models.schema_defs.phase4 import RuntimeTaskCreate, RuntimeTaskEventOut, RuntimeTaskListResponse, RuntimeTaskOut
from app.services.realtime import redis_runtime_task_events_enabled, subscribe_runtime_task_events
from app.services.tasks import RuntimeTaskQueue

router = APIRouter(prefix="/runtime-tasks", dependencies=[Depends(require_admin_auth)])


@router.post("", response_model=RuntimeTaskOut)
def enqueue_runtime_task(payload: RuntimeTaskCreate, db: Session = Depends(get_db)) -> RuntimeTaskOut:
    return RuntimeTaskQueue(db).enqueue(payload)


@router.get("", response_model=RuntimeTaskListResponse)
def list_runtime_tasks(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status: str | None = Query(default=None, max_length=24),
    db: Session = Depends(get_db),
) -> RuntimeTaskListResponse:
    return RuntimeTaskQueue(db).list(limit=limit, offset=offset, status=status)


@router.get("/{task_id}", response_model=RuntimeTaskOut)
def get_runtime_task(task_id: int, db: Session = Depends(get_db)) -> RuntimeTaskOut:
    try:
        return RuntimeTaskQueue(db).get(task_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{task_id}/events", response_model=list[RuntimeTaskEventOut])
def list_runtime_task_events(
    task_id: int,
    after_id: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[RuntimeTaskEventOut]:
    return RuntimeTaskQueue(db).events(task_id, after_id=after_id)


@router.get("/{task_id}/stream")
def stream_runtime_task_events(
    task_id: int,
    after_id: int = Query(default=0, ge=0),
) -> StreamingResponse:
    def event_stream():
        cursor = after_id
        settings = get_settings()
        timeout_seconds = int(settings.runtime_event_stream_timeout_seconds or 360)
        poll_seconds = max(float(settings.runtime_event_stream_poll_seconds or 1.0), 0.2)
        deadline = time.monotonic() + timeout_seconds

        if redis_runtime_task_events_enabled():
            cursor, terminal, emitted = _db_catch_up(task_id, cursor, limit=100)
            for event in emitted:
                yield _sse(event)
            if terminal:
                return
            for payload in subscribe_runtime_task_events(
                task_id,
                timeout_seconds=timeout_seconds,
                heartbeat_seconds=max(poll_seconds, 1.0),
            ):
                if payload.get("heartbeat"):
                    cursor, terminal, emitted = _db_catch_up(task_id, cursor, limit=100)
                    for event in emitted:
                        yield _sse(event)
                    if terminal:
                        return
                    if not emitted:
                        yield ": heartbeat\n\n"
                    continue
                try:
                    event = RuntimeTaskEventOut.model_validate(payload)
                except Exception:
                    continue
                if event.id <= cursor:
                    continue
                cursor = event.id
                yield _sse(event)
                if _terminal(event.event_type):
                    return
            cursor, terminal, emitted = _db_catch_up(task_id, cursor, limit=100)
            for event in emitted:
                yield _sse(event)
            if terminal or time.monotonic() >= deadline:
                return

        while time.monotonic() < deadline:
            cursor, terminal, emitted = _db_catch_up(task_id, cursor, limit=50)
            for event in emitted:
                yield _sse(event)
            if terminal:
                return
            time.sleep(poll_seconds)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _sse(event: RuntimeTaskEventOut) -> str:
    return (
        f"id: {event.id}\n"
        f"event: {event.event_type}\n"
        f"data: {json.dumps(event.model_dump(mode='json'), ensure_ascii=False, separators=(',', ':'))}\n\n"
    )


def _terminal(event_type: str) -> bool:
    return event_type in {"succeeded", "failed", "cancelled"}


def _db_catch_up(task_id: int, cursor: int, *, limit: int) -> tuple[int, bool, list[RuntimeTaskEventOut]]:
    with SessionLocal() as stream_db:
        events = RuntimeTaskQueue(stream_db).events(task_id, after_id=cursor, limit=limit)
    terminal = False
    for event in events:
        cursor = max(cursor, event.id)
        terminal = terminal or _terminal(event.event_type)
    return cursor, terminal, events
