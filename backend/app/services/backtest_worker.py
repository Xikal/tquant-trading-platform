from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.entities import BacktestRun
from app.services.backtest_job_service import BacktestJobService, _safe_error_message


logger = logging.getLogger(__name__)

TERMINAL_STATUSES = {"succeeded", "failed", "cancelled", "deleted"}


@dataclass(frozen=True)
class BacktestWorkerResult:
    run_id: int
    status: str
    message: str = ""


class BacktestWorkerCancelToken:
    """Cooperative cancellation token backed by local state and DB status."""

    def __init__(
        self,
        *,
        run_id: int,
        session_factory: Callable[[], Session],
        max_duration_seconds: float | None,
    ) -> None:
        self.run_id = run_id
        self.session_factory = session_factory
        self.max_duration_seconds = max_duration_seconds
        self.started_monotonic = time.monotonic()
        self.timed_out = False
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    def is_cancelled(self) -> bool:
        if self._event.is_set():
            return True
        if self.max_duration_seconds is not None and self.max_duration_seconds > 0:
            if time.monotonic() - self.started_monotonic >= self.max_duration_seconds:
                self.timed_out = True
                return True
        return self._is_cancelled_in_db()

    def _is_cancelled_in_db(self) -> bool:
        try:
            with self.session_factory() as db:
                status = db.execute(
                    select(BacktestRun.status).where(BacktestRun.id == self.run_id)
                ).scalar_one_or_none()
        except Exception:
            logger.exception("failed to read backtest cancellation status: run_id=%s", self.run_id)
            return False
        return status == "cancelled"


class BacktestWorker:
    """Consumes persistent backtest jobs from the database queue."""

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session] = SessionLocal,
        max_duration_seconds: float | None = 60 * 60,
    ) -> None:
        self.session_factory = session_factory
        self.max_duration_seconds = max_duration_seconds

    def run_once(self) -> BacktestWorkerResult | None:
        timed_out = self._cancel_timed_out_running_job()
        if timed_out is not None:
            return timed_out

        run_id = self._claim_next_queued_job()
        if run_id is None:
            return None

        token = BacktestWorkerCancelToken(
            run_id=run_id,
            session_factory=self.session_factory,
            max_duration_seconds=self.max_duration_seconds,
        )
        BacktestJobService.register_cancel_token(run_id, token)
        try:
            return self._execute_claimed_job(run_id, token)
        finally:
            BacktestJobService.unregister_cancel_token(run_id)

    def run_forever(self, *, poll_interval_seconds: float = 5.0, stop_event: threading.Event | None = None) -> None:
        while stop_event is None or not stop_event.is_set():
            outcome = self.run_once()
            if outcome is None:
                time.sleep(max(poll_interval_seconds, 0.1))

    def _claim_next_queued_job(self) -> int | None:
        with self.session_factory() as db:
            running_id = db.execute(
                select(BacktestRun.id)
                .where(BacktestRun.status == "running", BacktestRun.deleted_at.is_(None))
                .order_by(BacktestRun.started_at.asc(), BacktestRun.id.asc())
                .limit(1)
            ).scalar_one_or_none()
            if running_id is not None:
                return None

            run = db.execute(
                select(BacktestRun.id)
                .where(BacktestRun.status == "queued", BacktestRun.deleted_at.is_(None))
                .order_by(BacktestRun.created_at.asc(), BacktestRun.id.asc())
                .limit(1)
            ).scalar_one_or_none()
            if run is None:
                return None

            now = _utcnow()
            claimed = db.execute(
                update(BacktestRun)
                .where(BacktestRun.id == run, BacktestRun.status == "queued")
                .values(
                    status="running",
                    started_at=now,
                    finished_at=None,
                    cancelled_at=None,
                    error_message="",
                    progress_pct=5.0,
                )
            )
            if claimed.rowcount != 1:
                db.rollback()
                return None
            db.commit()
            return int(run)

    def _execute_claimed_job(
        self,
        run_id: int,
        cancel_token: BacktestWorkerCancelToken,
    ) -> BacktestWorkerResult:
        with self.session_factory() as db:
            service = BacktestJobService(db)
            try:
                run = db.get(BacktestRun, run_id)
                if run is None or run.deleted_at is not None:
                    return BacktestWorkerResult(run_id=run_id, status="skipped", message="run not found")
                if run.status == "cancelled" or cancel_token.is_cancelled():
                    service._mark_cancelled(run)
                    return BacktestWorkerResult(run_id=run_id, status="cancelled")

                result = service._run_engine(run, cancel_token)
                terminal_status = self._terminal_status_before_persist(run.id)
                if terminal_status == "cancelled":
                    service._mark_cancelled(run)
                    return BacktestWorkerResult(run_id=run_id, status="cancelled")
                if terminal_status == "deleted":
                    return BacktestWorkerResult(run_id=run_id, status="deleted")
                service._persist_result(run.id, result)
                return self._finalize_after_persist(run_id, timed_out=cancel_token.timed_out)
            except Exception as exc:
                logger.exception("backtest worker failed: run_id=%s", run_id)
                db.rollback()
                self._mark_failed(run_id, _safe_error_message(exc))
                return BacktestWorkerResult(run_id=run_id, status="failed", message=_safe_error_message(exc))

    def _finalize_after_persist(self, run_id: int, *, timed_out: bool) -> BacktestWorkerResult:
        with self.session_factory() as db:
            run = db.get(BacktestRun, run_id)
            if run is None:
                return BacktestWorkerResult(run_id=run_id, status="missing")
            if timed_out:
                run.error_message = "回测执行超时"
            if run.status in TERMINAL_STATUSES:
                run.finished_at = run.finished_at or _utcnow()
                if run.status == "succeeded":
                    run.progress_pct = 100.0
                db.commit()
            return BacktestWorkerResult(
                run_id=run_id,
                status=run.status or "unknown",
                message=run.error_message or "",
            )

    def _cancel_timed_out_running_job(self) -> BacktestWorkerResult | None:
        if self.max_duration_seconds is None or self.max_duration_seconds <= 0:
            return None

        deadline = _utcnow() - timedelta(seconds=self.max_duration_seconds)
        with self.session_factory() as db:
            run = db.execute(
                select(BacktestRun)
                .where(
                    BacktestRun.status == "running",
                    BacktestRun.deleted_at.is_(None),
                    BacktestRun.started_at.is_not(None),
                    BacktestRun.started_at < deadline,
                )
                .order_by(BacktestRun.started_at.asc(), BacktestRun.id.asc())
                .limit(1)
            ).scalar_one_or_none()
            if run is None:
                return None

            run.status = "failed"
            run.error_message = "回测执行超时"
            run.finished_at = _utcnow()
            run.progress_pct = max(float(run.progress_pct or 0.0), 0.0)
            db.commit()
            return BacktestWorkerResult(run_id=run.id, status=run.status, message=run.error_message)

    def _terminal_status_before_persist(self, run_id: int) -> str:
        try:
            with self.session_factory() as db:
                status = db.execute(
                    select(BacktestRun.status).where(BacktestRun.id == run_id)
                ).scalar_one_or_none()
        except Exception:
            logger.exception("failed to read backtest terminal status before persist: run_id=%s", run_id)
            return ""
        return str(status or "")

    def _mark_failed(self, run_id: int, message: str) -> None:
        with self.session_factory() as db:
            run = db.get(BacktestRun, run_id)
            if run is None:
                return
            if run.status in TERMINAL_STATUSES and run.status != "running":
                return
            run.status = "failed"
            run.error_message = message
            run.finished_at = _utcnow()
            run.progress_pct = max(float(run.progress_pct or 0.0), 0.0)
            db.commit()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
