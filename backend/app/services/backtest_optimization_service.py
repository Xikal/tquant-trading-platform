from __future__ import annotations

import json
import threading
from datetime import datetime
from typing import Any, Callable

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.backtest_entities import BacktestOptimization
from app.models.schema_defs.backtest import (
    BacktestOptimizationCreate,
    BacktestOptimizationDetail,
    BacktestOptimizationListResponse,
    BacktestOptimizationSummary,
)
from app.services.backtest.data_provider import DailyBarDataProvider
from app.services.backtest.cancel_token import BacktestCancelToken
from app.services.backtest.engine import BacktestConfig, BacktestEngine
from app.services.backtest.optimizer import BacktestOptimizer


TERMINAL_STATUSES = {"succeeded", "failed", "cancelled", "deleted"}


class BacktestOptimizationService:
    """Persistent task service for Phase 2 parameter optimization."""

    _cancel_tokens: dict[int, BacktestCancelToken] = {}
    _token_lock = threading.Lock()

    def __init__(self, db: Session) -> None:
        self.db = db

    def create_task(self, payload: BacktestOptimizationCreate, *, owner_user_id: int | None) -> BacktestOptimizationDetail:
        request = _optimization_request(payload)
        task = BacktestOptimization(
            name=payload.name or f"{payload.strategy} 参数优化",
            owner_user_id=owner_user_id,
            status="queued",
            strategy_key=payload.strategy,
            train_start=payload.train_start,
            train_end=payload.train_end,
            test_start=payload.test_start,
            test_end=payload.test_end,
            optimization_target=payload.optimization_target,
            initial_cash=float(payload.initial_cash),
            execution_model=payload.execution_model,
            progress_pct=0.0,
            request_json=_json_dumps(request),
            result_json="{}",
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return self._detail(task)

    def list_tasks(
        self,
        *,
        owner_user_id: int | None,
        is_admin: bool,
        limit: int,
        offset: int,
        status_filter: str | None = None,
    ) -> BacktestOptimizationListResponse:
        statement = select(BacktestOptimization).where(BacktestOptimization.deleted_at.is_(None))
        count_statement = select(func.count()).select_from(BacktestOptimization).where(BacktestOptimization.deleted_at.is_(None))
        for condition in self._visibility_filters(owner_user_id=owner_user_id, is_admin=is_admin):
            statement = statement.where(condition)
            count_statement = count_statement.where(condition)
        if status_filter:
            statement = statement.where(BacktestOptimization.status == status_filter)
            count_statement = count_statement.where(BacktestOptimization.status == status_filter)
        rows = self.db.execute(
            statement.order_by(BacktestOptimization.id.desc()).offset(offset).limit(limit)
        ).scalars().all()
        total = int(self.db.execute(count_statement).scalar_one() or 0)
        return BacktestOptimizationListResponse(
            items=[self._summary(row) for row in rows],
            total=total,
            limit=limit,
            offset=offset,
        )

    def get_task(self, task_id: int, *, owner_user_id: int | None, is_admin: bool) -> BacktestOptimizationDetail:
        return self._detail(self._get_visible_task(task_id, owner_user_id=owner_user_id, is_admin=is_admin))

    def cancel_task(self, task_id: int, *, owner_user_id: int | None, is_admin: bool) -> BacktestOptimizationDetail:
        task = self._get_visible_task(task_id, owner_user_id=owner_user_id, is_admin=is_admin)
        if task.status not in {"queued", "running"}:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="当前优化任务状态不可取消")
        self.request_cancel(task.id)
        task.status = "cancelled"
        task.cancelled_at = datetime.utcnow()
        task.finished_at = task.finished_at or task.cancelled_at
        self.db.commit()
        self.db.refresh(task)
        return self._detail(task)

    def delete_task(self, task_id: int, *, owner_user_id: int | None, is_admin: bool) -> BacktestOptimizationDetail:
        task = self._get_visible_task(task_id, owner_user_id=owner_user_id, is_admin=is_admin)
        task.status = "deleted"
        task.deleted_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(task)
        return self._detail(task)

    def claim_next_task(self) -> int | None:
        running_id = self.db.execute(
            select(BacktestOptimization.id)
            .where(BacktestOptimization.status == "running", BacktestOptimization.deleted_at.is_(None))
            .order_by(BacktestOptimization.started_at.asc(), BacktestOptimization.id.asc())
            .limit(1)
        ).scalar_one_or_none()
        if running_id is not None:
            return None
        task_id = self.db.execute(
            select(BacktestOptimization.id)
            .where(BacktestOptimization.status == "queued", BacktestOptimization.deleted_at.is_(None))
            .order_by(BacktestOptimization.created_at.asc(), BacktestOptimization.id.asc())
            .limit(1)
        ).scalar_one_or_none()
        if task_id is None:
            return None
        claimed = self.db.execute(
            update(BacktestOptimization)
            .where(BacktestOptimization.id == task_id, BacktestOptimization.status == "queued")
            .values(
                status="running",
                started_at=datetime.utcnow(),
                finished_at=None,
                cancelled_at=None,
                error_message="",
                progress_pct=1.0,
            )
        )
        if claimed.rowcount != 1:
            self.db.rollback()
            return None
        self.db.commit()
        return int(task_id)

    def execute_claimed_task(self, task_id: int, cancel_token: BacktestCancelToken) -> BacktestOptimizationDetail:
        task = self.db.get(BacktestOptimization, task_id)
        if task is None or task.deleted_at is not None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="优化任务不存在")
        if task.status == "cancelled" or cancel_token.is_cancelled():
            task.status = "cancelled"
            task.cancelled_at = datetime.utcnow()
            task.finished_at = task.finished_at or task.cancelled_at
            self.db.commit()
            return self._detail(task)
        try:
            request = _json_dict(task.request_json)
            config = _base_config(request)
            optimizer = BacktestOptimizer(BacktestEngine(DailyBarDataProvider(self.db)))
            report = optimizer.optimize_with_oos(
                config,
                param_grid=dict(request.get("param_grid") or {}),
                train_start=str(request.get("train_start") or task.train_start),
                train_end=str(request.get("train_end") or task.train_end),
                test_start=str(request.get("test_start") or task.test_start),
                test_end=str(request.get("test_end") or task.test_end),
                max_combinations=int(request.get("max_combinations") or 500),
                score_key=str(request.get("optimization_target") or task.optimization_target or "sharpe"),
                cancel_token=cancel_token,
                progress_callback=self._progress_callback(task.id),
            )
            self.db.refresh(task)
            if task.status == "cancelled" or cancel_token.is_cancelled():
                task.status = "cancelled"
                task.cancelled_at = task.cancelled_at or datetime.utcnow()
                task.finished_at = task.finished_at or task.cancelled_at
            else:
                result = report.to_dict()
                task.status = "succeeded"
                task.search_method = "random_sample" if report.sampled else "grid"
                task.result_json = _json_dumps(result)
                task.progress_pct = 100.0
                task.finished_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(task)
            return self._detail(task)
        except Exception as exc:
            self.db.rollback()
            task = self.db.get(BacktestOptimization, task_id)
            if task is not None:
                task.status = "failed"
                task.error_message = _safe_error_message(exc)
                task.finished_at = datetime.utcnow()
                self.db.commit()
                self.db.refresh(task)
                return self._detail(task)
            raise

    @classmethod
    def register_cancel_token(cls, task_id: int, token: BacktestCancelToken) -> None:
        with cls._token_lock:
            cls._cancel_tokens[task_id] = token

    @classmethod
    def unregister_cancel_token(cls, task_id: int) -> None:
        with cls._token_lock:
            cls._cancel_tokens.pop(task_id, None)

    @classmethod
    def request_cancel(cls, task_id: int) -> None:
        with cls._token_lock:
            token = cls._cancel_tokens.get(task_id)
        if token is not None:
            token.cancel()

    def _progress_callback(self, task_id: int) -> Callable[[float, str], None]:
        def update_progress(progress_pct: float, message: str) -> None:
            task = self.db.get(BacktestOptimization, task_id)
            if task is None or task.status != "running":
                return
            task.progress_pct = max(min(float(progress_pct), 99.0), float(task.progress_pct or 0.0))
            self.db.commit()

        return update_progress

    def _get_visible_task(self, task_id: int, *, owner_user_id: int | None, is_admin: bool) -> BacktestOptimization:
        statement = select(BacktestOptimization).where(
            BacktestOptimization.id == task_id,
            BacktestOptimization.deleted_at.is_(None),
        )
        for condition in self._visibility_filters(owner_user_id=owner_user_id, is_admin=is_admin):
            statement = statement.where(condition)
        task = self.db.execute(statement).scalar_one_or_none()
        if task is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="优化任务不存在")
        return task

    @staticmethod
    def _visibility_filters(*, owner_user_id: int | None, is_admin: bool):
        if is_admin:
            return []
        return [BacktestOptimization.owner_user_id == owner_user_id]

    @staticmethod
    def _summary(row: BacktestOptimization) -> BacktestOptimizationSummary:
        return BacktestOptimizationSummary(
            id=row.id,
            name=row.name or "",
            status=row.status or "queued",
            strategy_key=row.strategy_key or "",
            train_start=row.train_start or "",
            train_end=row.train_end or "",
            test_start=row.test_start or "",
            test_end=row.test_end or "",
            optimization_target=row.optimization_target or "sharpe",
            search_method=row.search_method or "grid",
            progress_pct=float(row.progress_pct or 0.0),
            owner_user_id=row.owner_user_id,
            created_at=row.created_at,
            updated_at=row.updated_at,
            started_at=row.started_at,
            finished_at=row.finished_at,
            cancelled_at=row.cancelled_at,
        )

    def _detail(self, row: BacktestOptimization) -> BacktestOptimizationDetail:
        summary = self._summary(row).model_dump()
        return BacktestOptimizationDetail(
            **summary,
            request=_json_dict(row.request_json),
            result=_json_dict(row.result_json),
            error_message=row.error_message or "",
        )


def _optimization_request(payload: BacktestOptimizationCreate) -> dict[str, Any]:
    return {
        "name": payload.name,
        "strategy_key": payload.strategy,
        "param_grid": payload.param_grid,
        "train_start": payload.train_start,
        "train_end": payload.train_end,
        "test_start": payload.test_start,
        "test_end": payload.test_end,
        "optimization_target": payload.optimization_target,
        "initial_cash": payload.initial_cash,
        "benchmark_symbol": payload.benchmark_symbol,
        "execution_model": payload.execution_model,
        "max_combinations": payload.max_combinations,
    }


def _base_config(request: dict[str, Any]) -> BacktestConfig:
    return BacktestConfig(
        start_date=str(request.get("train_start") or request.get("start_date") or ""),
        end_date=str(request.get("train_end") or request.get("end_date") or ""),
        benchmark_symbol=str(request.get("benchmark_symbol") or "000300"),
        strategies=[str(request.get("strategy_key") or request.get("strategy") or "")],
        initial_cash=float(request.get("initial_cash") or 100000.0),
        execution_model=str(request.get("execution_model") or "conservative_slippage"),
    )


def _json_dict(raw_value: str | None) -> dict[str, Any]:
    try:
        value = json.loads(raw_value or "{}")
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _json_dumps(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _safe_error_message(exc: Exception) -> str:
    message = str(exc).strip()
    return (message or "优化任务执行失败")[:240]
