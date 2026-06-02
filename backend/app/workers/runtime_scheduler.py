from __future__ import annotations

import logging
import signal
import threading

from app.core.config import get_settings
from app.core.logging_config import configure_logging
from app.runtime.background_jobs import shutdown_runtime_background_jobs, start_runtime_background_jobs


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
    start_runtime_background_jobs()
    try:
        _stop_event.wait()
    finally:
        shutdown_runtime_background_jobs(timeout=30)
        logger.info("runtime scheduler stopped")


if __name__ == "__main__":
    main()
