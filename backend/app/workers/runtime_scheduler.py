from __future__ import annotations

import logging
import signal
import threading

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.logging_config import configure_logging
from app.runtime.background_jobs import shutdown_runtime_background_jobs, start_runtime_background_jobs
from app.services.runtime_worker_health import record_platform_component_heartbeat


settings = get_settings()
configure_logging(structured=settings.structured_logs)
logger = logging.getLogger(__name__)
_stop_event = threading.Event()


def _request_shutdown(signum: int, _frame) -> None:  # noqa: ANN001
    logger.info("runtime scheduler received signal %s", signum)
    _stop_event.set()


def main() -> None:
    signal.signal(signal.SIGTERM, _request_shutdown)
    signal.signal(signal.SIGINT, _request_shutdown)
    logger.info("runtime scheduler starting")
    _record_scheduler_heartbeat(status="running")
    start_runtime_background_jobs()
    try:
        while not _stop_event.wait(30):
            _record_scheduler_heartbeat(status="running")
    finally:
        _record_scheduler_heartbeat(status="stopping")
        shutdown_runtime_background_jobs(timeout=30)
        logger.info("runtime scheduler stopped")


def _record_scheduler_heartbeat(*, status: str) -> None:
    try:
        with SessionLocal() as db:
            record_platform_component_heartbeat(
                db,
                component="runtime-scheduler",
                worker_id="runtime-scheduler",
                status=status,
            )
    except Exception:
        logger.exception("runtime scheduler heartbeat update failed")


if __name__ == "__main__":
    main()
