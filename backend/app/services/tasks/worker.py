from __future__ import annotations

import json
import logging
import socket
import time
from typing import Any

from app.core.database import SessionLocal
from app.services.tasks.handlers import TaskContext
from app.services.tasks.queue import RuntimeTaskQueue
from app.services.tasks.registry import TaskHandlerRegistry

logger = logging.getLogger(__name__)


class RuntimeTaskWorker:
    def __init__(
        self,
        *,
        registry: TaskHandlerRegistry,
        worker_id: str | None = None,
        poll_interval_seconds: float = 2.0,
    ) -> None:
        self.registry = registry
        self.worker_id = worker_id or f"worker-{socket.gethostname()}"
        self.poll_interval_seconds = max(float(poll_interval_seconds), 0.2)

    def run_once(self) -> bool:
        with SessionLocal() as db:
            queue = RuntimeTaskQueue(db)
            task = queue.claim_next(worker_id=self.worker_id, task_types=self.registry.task_types())
            if task is None:
                return False
            task_id = int(task.id)
            task_type = str(task.task_type)
            context = TaskContext(
                task_id=task_id,
                task_type=task_type,
                payload=_json_payload(task.payload_json),
                db=db,
                queue=queue,
                worker_id=self.worker_id,
            )
            try:
                context.progress(2.0, "任务已被 Worker 接收", {"worker_id": self.worker_id})
                result = self.registry.get(task_type)(context)
                payload = dict(result or {})
                if context.artifacts:
                    payload.setdefault("artifacts", context.artifacts)
                queue.mark_succeeded(task_id, payload)
            except Exception as exc:
                logger.exception("runtime task worker failed: id=%s type=%s", task_id, task_type)
                db.rollback()
                queue.mark_failed(task_id, str(exc), retryable=True)
            return True

    def run_forever(self) -> None:
        logger.info("runtime task worker started: worker_id=%s task_types=%s", self.worker_id, self.registry.task_types())
        while True:
            did_work = self.run_once()
            if not did_work:
                time.sleep(self.poll_interval_seconds)


def _json_payload(raw: str) -> dict[str, Any]:
    try:
        value = json.loads(raw or "{}")
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}
