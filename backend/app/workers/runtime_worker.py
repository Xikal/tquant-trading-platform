from __future__ import annotations

import logging
import socket
import time
from typing import Any

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.services.agent_daily_workflow_service import AgentDailyWorkflowService
from app.services.monitor_snapshot_cache import build_and_store_monitor_snapshot
from app.services.tasks import RuntimeTaskQueue

logger = logging.getLogger(__name__)


class RuntimeWorker:
    """Standalone runtime worker for non-request tasks."""

    def __init__(self, *, worker_id: str | None = None, poll_interval_seconds: float | None = None) -> None:
        settings = get_settings()
        self.worker_id = worker_id or f"runtime-{socket.gethostname()}"
        self.poll_interval_seconds = (
            poll_interval_seconds
            if poll_interval_seconds is not None
            else float(settings.runtime_worker_poll_interval_seconds)
        )

    def run_once(self) -> bool:
        with SessionLocal() as db:
            queue = RuntimeTaskQueue(db)
            task = queue.claim_next(worker_id=self.worker_id)
            if task is None:
                return False
            try:
                result = _execute_task(task.task_type, _json_payload(task.payload_json), db)
                queue.mark_succeeded(task.id, result)
            except Exception as exc:
                logger.exception("runtime task failed: id=%s type=%s", task.id, task.task_type)
                queue.mark_failed(task.id, str(exc), retryable=True)
            return True

    def run_forever(self) -> None:
        logger.info("runtime worker started: %s", self.worker_id)
        while True:
            did_work = self.run_once()
            if not did_work:
                time.sleep(self.poll_interval_seconds)


def _execute_task(task_type: str, payload: dict[str, Any], db) -> dict[str, Any]:  # noqa: ANN001
    if task_type == "noop":
        return {"ok": True, "message": "noop completed"}
    if task_type == "agent_daily_report_push":
        channel = str(payload.get("channel") or "feishu")
        response = AgentDailyWorkflowService().push_daily_report(db, channel=channel)
        return response.model_dump() if hasattr(response, "model_dump") else dict(response)
    if task_type == "monitor_snapshot_refresh":
        user_id = int(payload.get("user_id") or 0)
        priority_limit = int(payload.get("priority_limit") or 12)
        if user_id <= 0:
            raise ValueError("monitor snapshot refresh requires user_id")
        return build_and_store_monitor_snapshot(
            db,
            user_id=user_id,
            priority_limit=max(1, min(priority_limit, 30)),
        )
    raise ValueError(f"未知任务类型: {task_type}")


def _json_payload(raw: str) -> dict[str, Any]:
    import json

    try:
        value = json.loads(raw or "{}")
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    RuntimeWorker().run_forever()


if __name__ == "__main__":
    main()
