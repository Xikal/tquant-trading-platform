from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Literal

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.backtest_entities import BacktestOptimization, BacktestValidation
from app.services.backtest.cancel_token import DatabaseStatusCancelToken
from app.services.backtest_optimization_service import BacktestOptimizationService
from app.services.backtest_validation_service import BacktestValidationService


logger = logging.getLogger(__name__)
TaskKind = Literal["optimization", "validation"]


@dataclass(frozen=True)
class BacktestResearchWorkerResult:
    task_id: int
    task_kind: TaskKind
    status: str
    message: str = ""


class BacktestResearchWorker:
    """Single-step DB queue worker for optimization and validation tasks."""

    def __init__(self, *, session_factory: Callable[[], Session] = SessionLocal) -> None:
        self.session_factory = session_factory

    def run_once(self) -> BacktestResearchWorkerResult | None:
        optimization = self._run_optimization_once()
        if optimization is not None:
            return optimization
        return self._run_validation_once()

    def _run_optimization_once(self) -> BacktestResearchWorkerResult | None:
        with self.session_factory() as db:
            service = BacktestOptimizationService(db)
            task_id = service.claim_next_task()
            if task_id is None:
                return None
            token = DatabaseStatusCancelToken(
                model=BacktestOptimization,
                row_id=task_id,
                session_factory=self.session_factory,
                log_label="backtest optimization task",
            )
            BacktestOptimizationService.register_cancel_token(task_id, token)
            try:
                detail = service.execute_claimed_task(task_id, token)
                return BacktestResearchWorkerResult(
                    task_id=task_id,
                    task_kind="optimization",
                    status=detail.status,
                    message=detail.error_message,
                )
            finally:
                BacktestOptimizationService.unregister_cancel_token(task_id)

    def _run_validation_once(self) -> BacktestResearchWorkerResult | None:
        with self.session_factory() as db:
            service = BacktestValidationService(db)
            task_id = service.claim_next_task()
            if task_id is None:
                return None
            token = DatabaseStatusCancelToken(
                model=BacktestValidation,
                row_id=task_id,
                session_factory=self.session_factory,
                log_label="backtest validation task",
            )
            BacktestValidationService.register_cancel_token(task_id, token)
            try:
                detail = service.execute_claimed_task(task_id, token)
                return BacktestResearchWorkerResult(
                    task_id=task_id,
                    task_kind="validation",
                    status=detail.status,
                    message=detail.error_message,
                )
            finally:
                BacktestValidationService.unregister_cancel_token(task_id)
