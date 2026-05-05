from __future__ import annotations

import json
import logging
import math
import threading
from datetime import datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import BacktestRun
from app.models.backtest_entities import BacktestDailySnapshot, BacktestTrade
from app.models.schema_defs.backtest import (
    BacktestAttributionResponse,
    BacktestCompareRequest,
    BacktestCompareResponse,
    BacktestEquityPoint,
    BacktestMonthlyReturnsResponse,
    BacktestRunCreate,
    BacktestRunDetail,
    BacktestRunListResponse,
    BacktestRunSummary,
    BacktestStrategyCorrelationResponse,
    BacktestTradeOut,
    BacktestTradesResponse,
)
from app.services.backtest.data_provider import DailyBarDataProvider
from app.services.backtest.cancel_token import BacktestCancelToken
from app.services.backtest.engine import BacktestConfig, BacktestEngine, BacktestResult
from app.services.backtest.persistence import BacktestResultPersistence


logger = logging.getLogger(__name__)


class BacktestJobService:
    """Persistent API facade for v2 backtest jobs."""

    _cancel_tokens: dict[int, BacktestCancelToken] = {}
    _token_lock = threading.Lock()

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
                "max_duration_seconds": payload.max_duration_seconds,
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
            max_duration_seconds=int(payload.max_duration_seconds),
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
        benchmark_nav = 1.0
        points: list[BacktestEquityPoint] = []
        for index, row in enumerate(rows):
            if index > 0:
                benchmark_nav *= 1 + float(row.benchmark_return_pct or 0.0) / 100
            points.append(
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
                    benchmark_nav=benchmark_nav,
                    payload=_json_dict(row.payload_json),
                )
            )
        return points

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
        self.request_cancel(run.id)
        run.status = "cancelled"
        run.cancelled_at = datetime.utcnow()
        run.finished_at = run.finished_at or run.cancelled_at
        run.progress_pct = max(float(run.progress_pct or 0.0), 0.0)
        self.db.commit()
        self.db.refresh(run)
        return self._detail(run)

    @classmethod
    def register_cancel_token(cls, run_id: int, token: BacktestCancelToken) -> None:
        with cls._token_lock:
            cls._cancel_tokens[run_id] = token

    @classmethod
    def unregister_cancel_token(cls, run_id: int) -> None:
        with cls._token_lock:
            cls._cancel_tokens.pop(run_id, None)

    @classmethod
    def request_cancel(cls, run_id: int) -> None:
        with cls._token_lock:
            token = cls._cancel_tokens.get(run_id)
        if token is not None:
            token.cancel()

    def _run_engine(self, run: BacktestRun, cancel_token: BacktestCancelToken) -> BacktestResult:
        params = _json_dict(run.params_json)
        config = BacktestConfig(
            start_date=str(run.start_date or params.get("start_date") or ""),
            end_date=str(run.end_date or params.get("end_date") or ""),
            benchmark_symbol=str(run.benchmark_symbol or params.get("benchmark_symbol") or "000300"),
            strategies=_strategy_list(run.strategy_keys),
            initial_cash=float(run.initial_cash or 100000.0),
            execution_model=str(params.get("execution_model") or "conservative_slippage"),
            max_position_pct=float((params.get("risk_limits") or {}).get("max_position_pct") or 0.2),
            max_positions=int((params.get("risk_limits") or {}).get("max_positions") or 8),
            max_signals_per_day=int(params.get("max_signals_per_day") or 20),
            entry_delay_days=int(params.get("entry_delay_days") or 0),
            force_liquidate_at_end=bool(params.get("force_liquidate_at_end", True)),
            max_duration_seconds=int(run.max_duration_seconds or params.get("max_duration_seconds") or 1800),
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

    def get_monthly_returns(
        self,
        run_id: int,
        *,
        owner_user_id: int | None,
        is_admin: bool,
    ) -> BacktestMonthlyReturnsResponse:
        self._get_visible_run(run_id, owner_user_id=owner_user_id, is_admin=is_admin)
        rows = self.db.execute(
            select(BacktestDailySnapshot)
            .where(BacktestDailySnapshot.run_id == run_id)
            .order_by(BacktestDailySnapshot.trade_date.asc())
        ).scalars().all()
        return BacktestMonthlyReturnsResponse(run_id=run_id, items=_monthly_returns(rows))

    def get_attribution(
        self,
        run_id: int,
        *,
        owner_user_id: int | None,
        is_admin: bool,
    ) -> BacktestAttributionResponse:
        run = self._get_visible_run(run_id, owner_user_id=owner_user_id, is_admin=is_admin)
        result = _json_dict(run.result_json)
        attribution = _result_attribution(result)
        trades = self.db.execute(
            select(BacktestTrade).where(BacktestTrade.run_id == run_id).order_by(BacktestTrade.trade_date.asc())
        ).scalars().all()
        return BacktestAttributionResponse(
            run_id=run_id,
            strategy=_strategy_attribution(trades, result),
            industry=list(attribution.get("industry") or _bucket_trades(trades, "sector_name")),
            market_state=list(attribution.get("market_state") or _bucket_trades(trades, "market_state")),
            data_quality=list(attribution.get("data_quality") or []),
            notes=list(attribution.get("notes") or ["行业分类可能存在历史偏差"]),
        )

    def get_strategy_correlation(
        self,
        run_id: int,
        *,
        owner_user_id: int | None,
        is_admin: bool,
    ) -> BacktestStrategyCorrelationResponse:
        run = self._get_visible_run(run_id, owner_user_id=owner_user_id, is_admin=is_admin)
        trades = self.db.execute(
            select(BacktestTrade).where(BacktestTrade.run_id == run_id).order_by(BacktestTrade.trade_date.asc())
        ).scalars().all()
        strategies = _strategy_list(run.strategy_keys) or sorted({trade.strategy_key for trade in trades if trade.strategy_key})
        matrix = _strategy_correlation(strategies, trades)
        return BacktestStrategyCorrelationResponse(run_id=run_id, strategies=strategies, matrix=matrix)

    def compare_runs(
        self,
        payload: BacktestCompareRequest,
        *,
        owner_user_id: int | None,
        is_admin: bool,
    ) -> BacktestCompareResponse:
        items = []
        curves = []
        for run_id in payload.run_ids:
            run = self._get_visible_run(run_id, owner_user_id=owner_user_id, is_admin=is_admin)
            result = _json_dict(run.result_json)
            items.append(
                {
                    "run_id": run.id,
                    "name": run.name or "",
                    "status": run.status or "",
                    "strategy_keys": _strategy_list(run.strategy_keys),
                    "start_date": run.start_date,
                    "end_date": run.end_date,
                    "initial_cash": float(run.initial_cash or 0.0),
                    "final_equity": float(run.final_equity or 0.0),
                    "metrics": dict((result.get("metrics") or {}) if isinstance(result.get("metrics"), dict) else {}),
                }
            )
            curves.append({"run_id": run.id, "points": _compare_equity_points(run.id, self.db)})
        return BacktestCompareResponse(run_ids=payload.run_ids, items=items, equity_curves=curves)

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
        result = _json_dict(row.result_json)
        return BacktestRunDetail(
            **summary,
            params=_json_dict(row.params_json),
            result=result,
            attribution=_result_attribution(result),
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


def _result_attribution(result: dict[str, Any]) -> dict[str, Any]:
    attribution = result.get("attribution")
    if isinstance(attribution, dict):
        return attribution
    metrics = result.get("metrics")
    if isinstance(metrics, dict) and isinstance(metrics.get("attribution"), dict):
        return metrics["attribution"]
    return {}


def _monthly_returns(rows: list[BacktestDailySnapshot]) -> list[dict[str, Any]]:
    grouped: dict[str, list[BacktestDailySnapshot]] = {}
    for row in rows:
        grouped.setdefault(str(row.trade_date)[:7], []).append(row)
    output: list[dict[str, Any]] = []
    for month in sorted(grouped):
        items = grouped[month]
        start_equity = float(items[0].equity or 0.0)
        end_equity = float(items[-1].equity or 0.0)
        return_pct = 0.0 if start_equity <= 0 else (end_equity / start_equity - 1) * 100
        output.append(
            {
                "month": month,
                "start_equity": round(start_equity, 2),
                "end_equity": round(end_equity, 2),
                "return_pct": round(return_pct, 4),
                "trading_days": len(items),
            }
        )
    return output


def _strategy_attribution(trades: list[BacktestTrade], result: dict[str, Any]) -> list[dict[str, Any]]:
    metrics = result.get("metrics")
    by_strategy = metrics.get("by_strategy") if isinstance(metrics, dict) else None
    if isinstance(by_strategy, dict) and by_strategy:
        return [
            {"strategy_key": str(strategy), **dict(payload)}
            for strategy, payload in sorted(by_strategy.items())
            if isinstance(payload, dict)
        ]
    return [
        {"strategy_key": item["bucket"], **{key: value for key, value in item.items() if key != "bucket"}}
        for item in _bucket_trades(trades, "strategy_key")
    ]


def _bucket_trades(trades: list[BacktestTrade], attr_name: str) -> list[dict[str, Any]]:
    grouped: dict[str, list[BacktestTrade]] = {}
    for trade in trades:
        bucket = str(getattr(trade, attr_name, "") or "unknown")
        grouped.setdefault(bucket, []).append(trade)
    output = []
    for bucket, items in sorted(grouped.items()):
        winners = [trade for trade in items if float(trade.pnl_amount or 0.0) > 0]
        output.append(
            {
                "bucket": bucket,
                "trade_count": len(items),
                "win_count": len(winners),
                "win_rate_pct": round(len(winners) / max(len(items), 1) * 100, 4),
                "avg_return_pct": round(sum(float(trade.pnl_pct or 0.0) for trade in items) / max(len(items), 1), 4),
                "net_pnl": round(sum(float(trade.pnl_amount or 0.0) for trade in items), 2),
                "fee_amount": round(sum(float(trade.fee_amount or 0.0) for trade in items), 2),
            }
        )
    return output


def _compare_equity_points(run_id: int, db: Session) -> list[dict[str, Any]]:
    rows = db.execute(
        select(BacktestDailySnapshot)
        .where(BacktestDailySnapshot.run_id == run_id)
        .order_by(BacktestDailySnapshot.trade_date.asc())
    ).scalars().all()
    return [
        {
            "trade_date": row.trade_date,
            "equity": float(row.equity or 0.0),
            "daily_return_pct": float(row.daily_return_pct or 0.0),
            "drawdown_pct": float(row.drawdown_pct or 0.0),
        }
        for row in rows
    ]


def _strategy_correlation(strategies: list[str], trades: list[BacktestTrade]) -> list[dict[str, Any]]:
    normalized = sorted({strategy for strategy in strategies if strategy})
    if not normalized:
        normalized = sorted({trade.strategy_key for trade in trades if trade.strategy_key})
    dates = sorted({trade.trade_date for trade in trades})
    pnl_by_key = {(trade.strategy_key, trade.trade_date): 0.0 for trade in trades}
    for trade in trades:
        key = (trade.strategy_key, trade.trade_date)
        pnl_by_key[key] = pnl_by_key.get(key, 0.0) + float(trade.pnl_amount or 0.0)
    series = {
        strategy: [pnl_by_key.get((strategy, trade_date), 0.0) for trade_date in dates]
        for strategy in normalized
    }
    return [
        {
            "strategy_key": left,
            "correlations": {right: _pearson(series.get(left, []), series.get(right, []), same=left == right) for right in normalized},
        }
        for left in normalized
    ]


def _pearson(left: list[float], right: list[float], *, same: bool) -> float:
    if same:
        return 1.0
    pairs = list(zip(left, right))
    if len(pairs) < 2:
        return 0.0
    left_avg = sum(item[0] for item in pairs) / len(pairs)
    right_avg = sum(item[1] for item in pairs) / len(pairs)
    numerator = sum((left_item - left_avg) * (right_item - right_avg) for left_item, right_item in pairs)
    left_var = sum((left_item - left_avg) ** 2 for left_item, _ in pairs)
    right_var = sum((right_item - right_avg) ** 2 for _, right_item in pairs)
    denominator = math.sqrt(left_var * right_var)
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def _safe_error_message(exc: Exception) -> str:
    message = str(exc).strip()
    return (message or "回测执行失败")[:240]
