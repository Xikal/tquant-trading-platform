from __future__ import annotations

import logging
import threading
import time

from app.core.database import SessionLocal
from app.services.latest_data_close_refresh import enqueue_latest_data_close_refresh


logger = logging.getLogger(__name__)
_scheduler_thread: threading.Thread | None = None
_stop_event = threading.Event()


def start_latest_data_close_scheduler(*, interval_seconds: float = 30.0) -> None:
    global _scheduler_thread
    if _scheduler_thread and _scheduler_thread.is_alive():
        return
    _stop_event.clear()
    _scheduler_thread = threading.Thread(
        target=_run_loop,
        kwargs={"interval_seconds": max(5.0, interval_seconds)},
        name="latest-data-close-scheduler",
        daemon=True,
    )
    _scheduler_thread.start()
    logger.info("latest data close scheduler started")


def stop_latest_data_close_scheduler(timeout: float = 5.0) -> None:
    _stop_event.set()
    if _scheduler_thread and _scheduler_thread.is_alive():
        _scheduler_thread.join(timeout=timeout)


def run_latest_data_close_scheduler_once() -> dict:
    with SessionLocal() as db:
        return enqueue_latest_data_close_refresh(db)


def _run_loop(*, interval_seconds: float) -> None:
    while not _stop_event.is_set():
        try:
            result = run_latest_data_close_scheduler_once()
            if result.get("action") not in {"skip_before_close", "already_latest"}:
                logger.info("latest data close scheduler tick: %s", result)
        except Exception:
            logger.exception("latest data close scheduler tick failed")
        _stop_event.wait(interval_seconds)
