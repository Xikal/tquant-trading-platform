from __future__ import annotations

import json
import logging
import socket
import time
from typing import Any

from app.core.database import SessionLocal
from app.services.runtime_worker_health import record_platform_component_heartbeat
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
        component: str = "runtime-task-worker",
        poll_interval_seconds: float = 2.0,
    ) -> None:
        self.registry = registry
        self.worker_id = worker_id or f"worker-{socket.gethostname()}"
        self.component = component
        self.poll_interval_seconds = max(float(poll_interval_seconds), 0.2)

    def run_once(self) -> bool:
        with SessionLocal() as db:
            _record_component_heartbeat(db, component=self.component, worker_id=self.worker_id)
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
            log_extra = {"component": self.component, "task_id": task_id, "task_type": task_type}
            try:
                logger.info("runtime task worker task started", extra=log_extra)
                context.progress(2.0, "任务已被 Worker 接收", {"worker_id": self.worker_id})
                result = self.registry.get(task_type)(context)
                payload = dict(result or {})
                if context.artifacts:
                    payload.setdefault("artifacts", context.artifacts)
                queue.mark_succeeded(task_id, payload)
                logger.info("runtime task worker task succeeded", extra=log_extra)
            except Exception as exc:
                logger.exception("runtime task worker failed: id=%s type=%s", task_id, task_type, extra=log_extra)
                db.rollback()
                queue.mark_failed(task_id, str(exc), retryable=True)
            _record_component_heartbeat(db, component=self.component, worker_id=self.worker_id)
            return True

    def run_forever(self) -> None:
        logger.info(
            "runtime task worker started: worker_id=%s task_types=%s",
            self.worker_id,
            self.registry.task_types(),
            extra={"component": self.component},
        )
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


def _record_component_heartbeat(db, *, component: str, worker_id: str) -> None:  # noqa: ANN001
    try:
        record_platform_component_heartbeat(db, component=component, worker_id=worker_id)
    except Exception:
        logger.exception(
            "component heartbeat update failed: component=%s worker_id=%s",
            component,
            worker_id,
            extra={"component": component},
        )
