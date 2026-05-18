from __future__ import annotations

import logging
import threading
import time

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.timezone import beijing_now
from app.models.schema_defs.phase4 import RuntimeTaskCreate
from app.services.tasks import RuntimeTaskQueue


logger = logging.getLogger(__name__)
_scheduler_thread: threading.Thread | None = None
_stop_event = threading.Event()


def start_platform_autopilot_scheduler() -> None:
    settings = get_settings()
    if not settings.platform_autopilot_enabled:
        logger.info("platform autopilot scheduler disabled")
        return
    global _scheduler_thread
    if _scheduler_thread and _scheduler_thread.is_alive():
        return
    _stop_event.clear()
    _scheduler_thread = threading.Thread(
        target=_run_loop,
        kwargs={"interval_seconds": max(float(settings.platform_autopilot_interval_seconds), 60.0)},
        name="platform-autopilot-scheduler",
        daemon=True,
    )
    _scheduler_thread.start()
    logger.info("platform autopilot scheduler started")


def stop_platform_autopilot_scheduler(timeout: float = 5.0) -> None:
    _stop_event.set()
    if _scheduler_thread and _scheduler_thread.is_alive():
        _scheduler_thread.join(timeout=timeout)


def enqueue_platform_autopilot_once(*, trigger: str = "scheduled") -> dict:
    settings = get_settings()
    bucket = _bucket(settings.platform_autopilot_interval_seconds)
    with SessionLocal() as db:
        task = RuntimeTaskQueue(db).enqueue(
            RuntimeTaskCreate(
	                task_type="hermes_platform_autopilot",
	                payload={
	                    "auto_repair": True,
	                    "notify": bool(settings.platform_autopilot_notify_enabled),
	                    "trigger": trigger,
	                },
                priority=15,
                idempotency_key=f"hermes_platform_autopilot:{bucket}",
                max_attempts=2,
            )
        )
        return {"task_id": task.id, "status": task.status, "bucket": bucket}


def _run_loop(*, interval_seconds: float) -> None:
    while not _stop_event.is_set():
        try:
            result = enqueue_platform_autopilot_once()
            logger.info("platform autopilot scheduler tick: %s", result)
        except Exception:
            logger.exception("platform autopilot scheduler tick failed")
        _stop_event.wait(interval_seconds)


def _bucket(interval_seconds: int | float) -> str:
    now = beijing_now()
    seconds = max(int(interval_seconds or 300), 60)
    slot = (now.hour * 3600 + now.minute * 60 + now.second) // seconds
    return f"{now.strftime('%Y%m%d')}:{slot}"
