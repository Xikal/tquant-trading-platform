from __future__ import annotations

import json
import time

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.admin_auth import require_admin_auth
from app.core.database import get_db
from app.models.schema_defs.phase4 import RuntimeTaskCreate, RuntimeTaskEventOut, RuntimeTaskListResponse, RuntimeTaskOut
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
def stream_runtime_task_events(task_id: int, db: Session = Depends(get_db)) -> StreamingResponse:
    def event_stream():
        after_id = 0
        for _ in range(360):
            events = RuntimeTaskQueue(db).events(task_id, after_id=after_id, limit=50)
            for event in events:
                after_id = max(after_id, event.id)
                yield f"id: {event.id}\nevent: {event.event_type}\ndata: {json.dumps(event.model_dump(), default=str, ensure_ascii=False)}\n\n"
                if event.event_type in {"succeeded", "failed", "cancelled"}:
                    return
            time.sleep(1)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
