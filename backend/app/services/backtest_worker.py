from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.entities import BacktestRun
from app.services.backtest.cancel_token import BacktestCancelToken, TimedDatabaseStatusCancelToken
from app.services.backtest.concurrency import backtest_execution_slot, max_concurrent_backtests
from app.services.backtest.queue_lock import backtest_claim_lock
from app.services.backtest_job_service import BacktestJobService, _safe_error_message


logger = logging.getLogger(__name__)

TERMINAL_STATUSES = {"succeeded", "failed", "cancelled", "timeout", "deleted"}


@dataclass(frozen=True)
class BacktestWorkerResult:
    run_id: int
    status: str
    message: str = ""


class BacktestWorker:
    """Consumes persistent backtest jobs from the database queue."""

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session] = SessionLocal,
        max_duration_seconds: float | None = 1800,
    ) -> None:
        self.session_factory = session_factory
        self.max_duration_seconds = max_duration_seconds

    def run_once(self) -> BacktestWorkerResult | None:
        timed_out = self._cancel_timed_out_running_job()
        if timed_out is not None:
            return timed_out

        with backtest_execution_slot() as acquired:
            if not acquired:
                return None
            run_id = self._claim_next_queued_job()
            if run_id is None:
                return None

            token = TimedDatabaseStatusCancelToken(
                model=BacktestRun,
                row_id=run_id,
                session_factory=self.session_factory,
                max_duration_seconds=self._run_max_duration_seconds(run_id),
                log_label="backtest run",
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
            with backtest_claim_lock(db) as acquired:
                if acquired is False:
                    return None
                return self._claim_next_queued_job_locked(db)

    def _claim_next_queued_job_locked(self, db: Session) -> int | None:
        max_concurrent = _max_concurrent_backtests()
        running_count = int(
            db.execute(
                select(func.count(BacktestRun.id)).where(
                    BacktestRun.status == "running",
                    BacktestRun.deleted_at.is_(None),
                )
            )
            .scalar_one()
            or 0
        )
        if running_count >= max_concurrent:
            return None
        running_id = db.execute(
            select(BacktestRun.id)
            .where(BacktestRun.status == "running", BacktestRun.deleted_at.is_(None))
            .order_by(BacktestRun.started_at.asc(), BacktestRun.id.asc())
            .limit(1)
        ).scalar_one_or_none()
        if running_id is not None and max_concurrent <= 1:
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

    def _run_max_duration_seconds(self, run_id: int) -> float | None:
        with self.session_factory() as db:
            value = db.execute(
                select(BacktestRun.max_duration_seconds).where(BacktestRun.id == run_id)
            ).scalar_one_or_none()
        if value is None or value <= 0:
            return self.max_duration_seconds
        if self.max_duration_seconds is None or self.max_duration_seconds <= 0:
            return float(value)
        return min(float(value), float(self.max_duration_seconds))

    def _execute_claimed_job(
        self,
        run_id: int,
        cancel_token: BacktestCancelToken,
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
                if terminal_status == "timeout":
                    return BacktestWorkerResult(run_id=run_id, status="timeout", message="回测执行超时")
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
                run.status = "timeout"
                run.error_message = "回测执行超时"
                run.finished_at = run.finished_at or _utcnow()
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

            run.status = "timeout"
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
            run.status = "timeout" if "超时" in message else "failed"
            run.error_message = message
            run.finished_at = _utcnow()
            run.progress_pct = max(float(run.progress_pct or 0.0), 0.0)
            db.commit()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _max_concurrent_backtests() -> int:
    return max_concurrent_backtests()
