from __future__ import annotations

import json
import logging
import threading
from datetime import datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.entities import BacktestRun
from app.models.backtest_entities import BacktestDailySnapshot, BacktestTrade
from app.models.schema_defs.backtest import (
    BacktestEquityPoint,
    BacktestRunCreate,
    BacktestRunDetail,
    BacktestRunListResponse,
    BacktestRunSummary,
    BacktestTradeOut,
    BacktestTradesResponse,
)
from app.services.backtest.data_provider import DailyBarDataProvider
from app.services.backtest.engine import BacktestConfig, BacktestEngine
from app.services.backtest.persistence import BacktestResultPersistence


logger = logging.getLogger(__name__)


class _RunCancelToken:
    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    def is_cancelled(self) -> bool:
        return self._event.is_set()


class BacktestJobService:
    """Persistent API facade for v2 backtest jobs."""

    _cancel_tokens: dict[int, _RunCancelToken] = {}
    _thread_lock = threading.Lock()

    def __init__(self, db: Session) -> None:
        self.db = db

    def create_run(self, payload: BacktestRunCreate, owner_user_id: int | None) -> BacktestRunDetail:
        params = dict(payload.params)
        params.update(
            {
                "strategy_keys": payload.strategy_keys,
                "start_date": payload.start_date,
                "end_date": payload.end_date,
                "benchmark_symbol": payload.benchmark_symbol,
            }
        )
        run = BacktestRun(
            name=payload.name or self._default_name(payload),
            owner_user_id=owner_user_id,
            status="queued",
            strategy_keys=",".join(payload.strategy_keys),
            start_date=payload.start_date,
            end_date=payload.end_date,
            benchmark_symbol=payload.benchmark_symbol,
            initial_cash=float(payload.initial_cash),
            final_equity=float(payload.initial_cash),
            progress_pct=0.0,
            dataset_manifest_id=payload.dataset_manifest_id,
            engine_version=payload.engine_version,
            strategy_version=payload.strategy_version,
            data_version=payload.data_version,
            fee_model_version=payload.fee_model_version,
            slippage_bps=float(payload.slippage_bps),
            params_json=_json_dumps(params),
            result_json="{}",
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        self._start_background_run(run.id)
        return self._detail(run)

    def list_runs(
        self,
        *,
        owner_user_id: int | None,
        is_admin: bool,
        limit: int,
        offset: int,
        status_filter: str | None = None,
        strategy_key: str | None = None,
    ) -> BacktestRunListResponse:
        statement = select(BacktestRun).where(BacktestRun.deleted_at.is_(None))
        count_statement = select(func.count()).select_from(BacktestRun).where(BacktestRun.deleted_at.is_(None))
        filters = self._visibility_filters(owner_user_id=owner_user_id, is_admin=is_admin)
        for condition in filters:
            statement = statement.where(condition)
            count_statement = count_statement.where(condition)
        if status_filter:
            statement = statement.where(BacktestRun.status == status_filter)
            count_statement = count_statement.where(BacktestRun.status == status_filter)
        if strategy_key:
            pattern = f"%{strategy_key}%"
            statement = statement.where(BacktestRun.strategy_keys.like(pattern))
            count_statement = count_statement.where(BacktestRun.strategy_keys.like(pattern))
        rows = self.db.execute(
            statement.order_by(BacktestRun.id.desc()).offset(offset).limit(limit)
        ).scalars().all()
        total = int(self.db.execute(count_statement).scalar_one() or 0)
        return BacktestRunListResponse(
            items=[self._summary(row) for row in rows],
            total=total,
            limit=limit,
            offset=offset,
        )

    def get_run(self, run_id: int, *, owner_user_id: int | None, is_admin: bool) -> BacktestRunDetail:
        return self._detail(self._get_visible_run(run_id, owner_user_id=owner_user_id, is_admin=is_admin))

    def get_equity(self, run_id: int, *, owner_user_id: int | None, is_admin: bool) -> list[BacktestEquityPoint]:
        self._get_visible_run(run_id, owner_user_id=owner_user_id, is_admin=is_admin)
        rows = self.db.execute(
            select(BacktestDailySnapshot)
            .where(BacktestDailySnapshot.run_id == run_id)
            .order_by(BacktestDailySnapshot.trade_date.asc())
        ).scalars().all()
        return [
            BacktestEquityPoint(
                trade_date=row.trade_date,
                cash=row.cash,
                market_value=row.market_value,
                equity=row.equity,
                daily_return_pct=row.daily_return_pct,
                drawdown_pct=row.drawdown_pct,
                exposure_pct=row.exposure_pct,
                positions_count=row.positions_count,
                turnover=row.turnover,
                benchmark_symbol=row.benchmark_symbol,
                benchmark_close=row.benchmark_close,
                benchmark_return_pct=row.benchmark_return_pct,
                payload=_json_dict(row.payload_json),
            )
            for row in rows
        ]

    def get_trades(
        self,
        run_id: int,
        *,
        owner_user_id: int | None,
        is_admin: bool,
        limit: int,
        offset: int,
    ) -> BacktestTradesResponse:
        self._get_visible_run(run_id, owner_user_id=owner_user_id, is_admin=is_admin)
        base = select(BacktestTrade).where(BacktestTrade.run_id == run_id)
        total = int(
            self.db.execute(
                select(func.count()).select_from(BacktestTrade).where(BacktestTrade.run_id == run_id)
            ).scalar_one()
            or 0
        )
        rows = self.db.execute(
            base.order_by(BacktestTrade.trade_date.asc(), BacktestTrade.id.asc()).offset(offset).limit(limit)
        ).scalars().all()
        return BacktestTradesResponse(
            run_id=run_id,
            items=[self._trade(row) for row in rows],
            total=total,
            limit=limit,
            offset=offset,
        )

    def cancel_run(self, run_id: int, *, owner_user_id: int | None, is_admin: bool) -> BacktestRunDetail:
        run = self._get_visible_run(run_id, owner_user_id=owner_user_id, is_admin=is_admin)
        if run.status not in {"queued", "running"}:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="当前回测状态不可取消")
        token = self._cancel_tokens.get(run.id)
        if token is not None:
            token.cancel()
        run.status = "cancelled"
        run.cancelled_at = datetime.utcnow()
        run.finished_at = run.finished_at or run.cancelled_at
        run.progress_pct = max(float(run.progress_pct or 0.0), 0.0)
        self.db.commit()
        self.db.refresh(run)
        return self._detail(run)

    @classmethod
    def _start_background_run(cls, run_id: int) -> None:
        token = _RunCancelToken()
        with cls._thread_lock:
            cls._cancel_tokens[run_id] = token
        thread = threading.Thread(
            target=cls._execute_run,
            args=(run_id, token),
            name=f"backtest-run-{run_id}",
            daemon=True,
        )
        thread.start()

    @classmethod
    def _execute_run(cls, run_id: int, cancel_token: _RunCancelToken) -> None:
        with SessionLocal() as db:
            service = cls(db)
            try:
                run = db.get(BacktestRun, run_id)
                if run is None or run.deleted_at is not None:
                    return
                if run.status == "cancelled" or cancel_token.is_cancelled():
                    service._mark_cancelled(run)
                    return
                run.status = "running"
                run.started_at = datetime.utcnow()
                run.progress_pct = 5.0
                db.commit()
                result = service._run_engine(run, cancel_token)
                service._persist_result(run.id, result)
            except Exception as exc:
                logger.exception("backtest run failed: run_id=%s", run_id)
                db.rollback()
                run = db.get(BacktestRun, run_id)
                if run is not None:
                    run.status = "failed"
                    run.error_message = _safe_error_message(exc)
                    run.finished_at = datetime.utcnow()
                    run.progress_pct = max(float(run.progress_pct or 0.0), 0.0)
                    db.commit()
            finally:
                with cls._thread_lock:
                    cls._cancel_tokens.pop(run_id, None)

    def _run_engine(self, run: BacktestRun, cancel_token: _RunCancelToken) -> BacktestResult:
        params = _json_dict(run.params_json)
        config = BacktestConfig(
            start_date=str(run.start_date or params.get("start_date") or ""),
            end_date=str(run.end_date or params.get("end_date") or ""),
            strategies=_strategy_list(run.strategy_keys),
            initial_cash=float(run.initial_cash or 100000.0),
            execution_model=str(params.get("execution_model") or "conservative_slippage"),
            max_position_pct=float((params.get("risk_limits") or {}).get("max_position_pct") or 0.2),
            max_positions=int((params.get("risk_limits") or {}).get("max_positions") or 8),
            max_signals_per_day=int(params.get("max_signals_per_day") or 20),
            entry_delay_days=int(params.get("entry_delay_days") or 0),
            force_liquidate_at_end=bool(params.get("force_liquidate_at_end", True)),
        )
        engine = BacktestEngine(DailyBarDataProvider(self.db))
        return engine.run(config, cancel_token=cancel_token)

    def _persist_result(self, run_id: int, result: BacktestResult) -> None:
        run = self.db.get(BacktestRun, run_id)
        if run is None:
            return
        BacktestResultPersistence(self.db).persist(run, result)

    def _mark_cancelled(self, run: BacktestRun) -> None:
        run.status = "cancelled"
        run.cancelled_at = datetime.utcnow()
        run.finished_at = run.finished_at or run.cancelled_at
        self.db.commit()

    def delete_run(self, run_id: int, *, owner_user_id: int | None, is_admin: bool) -> BacktestRunDetail:
        run = self._get_visible_run(run_id, owner_user_id=owner_user_id, is_admin=is_admin)
        run.status = "deleted"
        run.deleted_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(run)
        return self._detail(run)

    def _get_visible_run(self, run_id: int, *, owner_user_id: int | None, is_admin: bool) -> BacktestRun:
        statement = select(BacktestRun).where(BacktestRun.id == run_id, BacktestRun.deleted_at.is_(None))
        for condition in self._visibility_filters(owner_user_id=owner_user_id, is_admin=is_admin):
            statement = statement.where(condition)
        row = self.db.execute(statement).scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="回测任务不存在")
        return row

    @staticmethod
    def _visibility_filters(*, owner_user_id: int | None, is_admin: bool):
        if is_admin:
            return []
        return [BacktestRun.owner_user_id == owner_user_id]

    @staticmethod
    def _default_name(payload: BacktestRunCreate) -> str:
        strategies = ",".join(payload.strategy_keys) or "all"
        return f"{strategies} {payload.start_date}-{payload.end_date}"

    @staticmethod
    def _summary(row: BacktestRun) -> BacktestRunSummary:
        return BacktestRunSummary(
            id=row.id,
            name=row.name or "",
            status=row.status or "queued",
            strategy_keys=_strategy_list(row.strategy_keys),
            start_date=row.start_date,
            end_date=row.end_date,
            initial_cash=float(row.initial_cash or 0.0),
            final_equity=float(row.final_equity or 0.0),
            progress_pct=float(row.progress_pct or 0.0),
            benchmark_symbol=row.benchmark_symbol or "",
            owner_user_id=row.owner_user_id,
            created_at=row.created_at,
            updated_at=row.updated_at,
            started_at=row.started_at,
            finished_at=row.finished_at,
            cancelled_at=row.cancelled_at,
        )

    def _detail(self, row: BacktestRun) -> BacktestRunDetail:
        summary = self._summary(row).model_dump()
        return BacktestRunDetail(
            **summary,
            params=_json_dict(row.params_json),
            result=_json_dict(row.result_json),
            dataset_manifest_id=row.dataset_manifest_id,
            engine_version=row.engine_version or "",
            strategy_version=row.strategy_version or "",
            data_version=row.data_version or "",
            fee_model_version=row.fee_model_version or "",
            slippage_bps=float(row.slippage_bps or 0.0),
            error_message=row.error_message or "",
        )

    @staticmethod
    def _trade(row: BacktestTrade) -> BacktestTradeOut:
        return BacktestTradeOut(
            id=row.id,
            run_id=row.run_id,
            order_id=row.order_id,
            trade_date=row.trade_date,
            symbol=row.symbol,
            name=row.name,
            side=row.side,
            strategy_key=row.strategy_key,
            signal_state=row.signal_state,
            quantity=row.quantity,
            price=row.price,
            gross_amount=row.gross_amount,
            fee_amount=row.fee_amount,
            slippage_amount=row.slippage_amount,
            net_amount=row.net_amount,
            pnl_amount=row.pnl_amount,
            pnl_pct=row.pnl_pct,
            holding_days=row.holding_days,
            entry_reason=row.entry_reason,
            exit_reason=row.exit_reason,
            market_state=row.market_state,
            sector_name=row.sector_name,
            payload=_json_dict(row.payload_json),
            created_at=row.created_at,
        )


def _strategy_list(raw_value: str | None) -> list[str]:
    return [item.strip() for item in (raw_value or "").split(",") if item.strip()]


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
    return (message or "回测执行失败")[:240]
