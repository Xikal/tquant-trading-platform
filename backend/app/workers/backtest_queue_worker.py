from __future__ import annotations

import logging
import os
import threading
import time

from app.services.backtest_research_worker import BacktestResearchWorker
from app.services.backtest_worker import BacktestWorker


logger = logging.getLogger(__name__)


class BacktestQueueWorker:
    """Consumes both normal backtests and research optimization tasks."""

    def __init__(
        self,
        *,
        max_duration_seconds: float | None = None,
        poll_interval_seconds: float = 5.0,
    ) -> None:
        self.backtest_worker = BacktestWorker(max_duration_seconds=max_duration_seconds)
        self.research_worker = BacktestResearchWorker()
        self.poll_interval_seconds = max(float(poll_interval_seconds), 0.1)
        self._prefer_research_next = False

    def run_once(self) -> bool:
        if self._prefer_research_next:
            research_result = self.research_worker.run_once()
            if research_result is not None:
                self._prefer_research_next = False
                logger.info(
                    "回测研究任务处理完成: kind=%s id=%s status=%s message=%s",
                    research_result.task_kind,
                    research_result.task_id,
                    research_result.status,
                    research_result.message,
                )
                return True

        backtest_result = self.backtest_worker.run_once()
        if backtest_result is not None:
            self._prefer_research_next = True
            logger.info(
                "回测任务处理完成: id=%s status=%s message=%s",
                backtest_result.run_id,
                backtest_result.status,
                backtest_result.message,
            )
            return True

        research_result = self.research_worker.run_once()
        if research_result is not None:
            self._prefer_research_next = False
            logger.info(
                "回测研究任务处理完成: kind=%s id=%s status=%s message=%s",
                research_result.task_kind,
                research_result.task_id,
                research_result.status,
                research_result.message,
            )
            return True
        return False

    def run_forever(self, *, stop_event: threading.Event | None = None) -> None:
        logger.info("backtest queue worker started")
        while stop_event is None or not stop_event.is_set():
            if not self.run_once():
                time.sleep(self.poll_interval_seconds)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    raw_duration = os.getenv("BACKTEST_WORKER_MAX_DURATION", "3600")
    raw_interval = os.getenv("BACKTEST_WORKER_POLL_INTERVAL", "5")
    BacktestQueueWorker(
        max_duration_seconds=float(raw_duration) if raw_duration else None,
        poll_interval_seconds=float(raw_interval or 5),
    ).run_forever()


if __name__ == "__main__":
    main()
