from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Protocol, Type

from sqlalchemy import select
from sqlalchemy.orm import Session


logger = logging.getLogger(__name__)


class BacktestCancelToken(Protocol):
    timed_out: bool

    def cancel(self) -> None:
        ...

    def is_cancelled(self) -> bool:
        ...


class EventCancelToken:
    timed_out = False

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    def is_cancelled(self) -> bool:
        return self._event.is_set()


class DatabaseStatusCancelToken(EventCancelToken):
    """Cancellation token backed by an in-process event and a DB status row."""

    def __init__(
        self,
        *,
        model: Type,
        row_id: int,
        session_factory: Callable[[], Session],
        cancelled_status: str = "cancelled",
        log_label: str = "backtest task",
        db_poll_interval_seconds: float = 0.5,
    ) -> None:
        super().__init__()
        self.model = model
        self.row_id = int(row_id)
        self.session_factory = session_factory
        self.cancelled_status = cancelled_status
        self.log_label = log_label
        self.db_poll_interval_seconds = max(float(db_poll_interval_seconds or 0.0), 0.0)
        self._last_db_poll_at = 0.0
        self._last_db_cancelled = False

    def is_cancelled(self) -> bool:
        if super().is_cancelled():
            return True
        now = time.monotonic()
        if self._last_db_cancelled:
            return True
        if self.db_poll_interval_seconds > 0 and now - self._last_db_poll_at < self.db_poll_interval_seconds:
            return False
        self._last_db_poll_at = now
        try:
            with self.session_factory() as db:
                status = db.execute(select(self.model.status).where(self.model.id == self.row_id)).scalar_one_or_none()
        except Exception:
            logger.exception("failed to read %s cancellation status", self.log_label)
            return False
        self._last_db_cancelled = status == self.cancelled_status
        return self._last_db_cancelled


class TimedDatabaseStatusCancelToken(DatabaseStatusCancelToken):
    def __init__(self, *, max_duration_seconds: float | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.max_duration_seconds = max_duration_seconds
        self.started_monotonic = time.monotonic()
        self.timed_out = False

    def is_cancelled(self) -> bool:
        if self.max_duration_seconds is not None and self.max_duration_seconds > 0:
            if time.monotonic() - self.started_monotonic >= self.max_duration_seconds:
                self.timed_out = True
                return True
        return super().is_cancelled()
