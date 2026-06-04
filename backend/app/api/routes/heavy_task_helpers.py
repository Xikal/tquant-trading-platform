from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.models.schema_defs.phase4 import RuntimeTaskCreate, RuntimeTaskOut
from app.services.tasks import RuntimeTaskQueue


def enqueue_runtime_task(
    db: Session,
    *,
    task_type: str,
    payload: dict[str, Any],
    priority: int = 200,
    idempotency_key: str = "",
    max_attempts: int = 2,
) -> RuntimeTaskOut:
    return RuntimeTaskQueue(db).enqueue(
        RuntimeTaskCreate(
            task_type=task_type,
            payload=payload,
            priority=priority,
            idempotency_key=idempotency_key,
            max_attempts=max_attempts,
        )
    )


def queued_task_response(task: RuntimeTaskOut) -> JSONResponse:
    return JSONResponse(status_code=202, content=task.model_dump(mode="json"))
