from __future__ import annotations

from statistics import mean
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import BacktestTrade, DailyBarSnapshot, LowBuyResultSnapshot
from app.models.schema_defs.phase4 import (
    StrategyCapacityItem,
    StrategyCapacityPoint,
    StrategyCapacityRequest,
    StrategyCapacityResponse,
)
from app.services.quant.runtime_parameters import get_backtest_execution


class StrategyCapacityService:
    """Estimate strategy capacity under liquidity and market-impact assumptions."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def evaluate(self, payload: StrategyCapacityRequest) -> StrategyCapacityResponse:
        strategies = payload.strategies or self._default_strategies()
        params = get_backtest_execution()
        items = [
            self._evaluate_strategy(strategy_key=strategy, payload=payload, params=params)
            for strategy in strategies
        ]
        return StrategyCapacityResponse(
            generated_at=_now_text(),
            capital_levels=payload.capital_levels,
            items=items,
            assumptions={
                "impact_model": "Kyle Lambda + participation tier",
                "capital_levels": payload.capital_levels,
                "start_date": payload.start_date,
                "end_date": payload.end_date,
                "notes": [
                    "容量评估只用于资金规模约束，不构成交易承诺。",
                    "缺少成交样本时 base_edge_pct 使用 0，并标记为数据不足。",
                ],
            },
        )

    def _default_strategies(self) -> list[str]:
        rows = (
            self.db.execute(
                select(LowBuyResultSnapshot.strategy_key)
                .where(LowBuyResultSnapshot.strategy_key != "")
                .order_by(LowBuyResultSnapshot.updated_at.desc())
                .limit(50)
            )
            .scalars()
            .all()
        )
        result: list[str] = []
        for item in rows:
            if item not in result:
                result.append(str(item))
        return result[:8] or ["first_board", "volume_shrink"]

    def _evaluate_strategy(
        self,
        *,
        strategy_key: str,
        payload: StrategyCapacityRequest,
        params: dict[str, Any],
    ) -> StrategyCapacityItem:
        trades = self._load_trades(strategy_key, payload)
        symbols = sorted({row.symbol for row in trades if row.symbol})
        if not symbols:
            symbols = self._load_snapshot_symbols(strategy_key, payload)
        bars = self._load_bars(symbols, payload)
        avg_daily_amount = _safe_mean([float(row.amount or 0.0) for row in bars if float(row.amount or 0.0) > 0])
        base_edge_pct = _safe_mean([float(row.pnl_pct or 0.0) for row in trades])
        lambda_value = _kyle_lambda(bars)
        slippage_pct = _slippage_pct(params)
        curve = [
            _capacity_point(
                capital=float(capital),
                avg_daily_amount=avg_daily_amount,
                base_edge_pct=base_edge_pct,
                lambda_value=lambda_value,
                slippage_pct=slippage_pct,
                params=params,
            )
            for capital in payload.capital_levels
        ]
        notes: list[str] = []
        if not trades:
            notes.append("缺少该策略真实/回测成交样本，base_edge_pct 按 0 处理。")
        if avg_daily_amount <= 0:
            notes.append("缺少有效成交额数据，容量曲线按最保守冲击成本处理。")
        if lambda_value <= 0:
            notes.append("Kyle Lambda 不可用，主要依赖参与度分层冲击成本。")
        return StrategyCapacityItem(
            strategy_key=strategy_key,
            sample_count=len(trades),
            symbol_count=len(symbols),
            avg_daily_amount=round(avg_daily_amount, 2),
            base_edge_pct=round(base_edge_pct, 4),
            kyle_lambda=lambda_value,
            curve=curve,
            notes=notes,
        )

    def _load_trades(self, strategy_key: str, payload: StrategyCapacityRequest) -> list[BacktestTrade]:
        statement = select(BacktestTrade).where(BacktestTrade.strategy_key == strategy_key)
        if payload.start_date:
            statement = statement.where(BacktestTrade.trade_date >= payload.start_date)
        if payload.end_date:
            statement = statement.where(BacktestTrade.trade_date <= payload.end_date)
        return self.db.execute(statement.order_by(BacktestTrade.id.desc()).limit(payload.trade_limit)).scalars().all()

    def _load_snapshot_symbols(self, strategy_key: str, payload: StrategyCapacityRequest) -> list[str]:
        statement = select(LowBuyResultSnapshot.symbol).where(LowBuyResultSnapshot.strategy_key == strategy_key)
        if payload.end_date:
            statement = statement.where(LowBuyResultSnapshot.latest_trade_date <= payload.end_date)
        rows = self.db.execute(statement.order_by(LowBuyResultSnapshot.updated_at.desc()).limit(80)).scalars().all()
        result: list[str] = []
        for symbol in rows:
            if symbol and symbol not in result:
                result.append(str(symbol))
        return result[:40]

    def _load_bars(self, symbols: list[str], payload: StrategyCapacityRequest) -> list[DailyBarSnapshot]:
        if not symbols:
            return []
        statement = select(DailyBarSnapshot).where(DailyBarSnapshot.symbol.in_(symbols))
        if payload.start_date:
            statement = statement.where(DailyBarSnapshot.trade_date >= payload.start_date)
        if payload.end_date:
            statement = statement.where(DailyBarSnapshot.trade_date <= payload.end_date)
        return self.db.execute(statement.order_by(DailyBarSnapshot.trade_date.desc()).limit(payload.bar_limit)).scalars().all()


def _capacity_point(
    *,
    capital: float,
    avg_daily_amount: float,
    base_edge_pct: float,
    lambda_value: float,
    slippage_pct: float,
    params: dict[str, Any],
) -> StrategyCapacityPoint:
    participation = capital / avg_daily_amount if avg_daily_amount > 0 else 1.0
    kyle_impact_pct = max(lambda_value * capital * 100.0, 0.0)
    tier_impact_pct = _impact_rate(participation, params) * 100.0
    impact_pct = max(kyle_impact_pct, tier_impact_pct)
    net_edge_pct = base_edge_pct - impact_pct - slippage_pct
    if avg_daily_amount <= 0 or participation >= 0.10 or net_edge_pct < 0:
        status = "过载"
    elif participation >= 0.05:
        status = "谨慎"
    else:
        status = "可承载"
    return StrategyCapacityPoint(
        capital=round(capital, 2),
        participation_pct=round(participation * 100.0, 4),
        expected_edge_pct=round(base_edge_pct, 4),
        kyle_impact_pct=round(kyle_impact_pct, 4),
        impact_cost_pct=round(impact_pct, 4),
        slippage_cost_pct=round(slippage_pct, 4),
        net_edge_pct=round(net_edge_pct, 4),
        capacity_status=status,
    )


def _kyle_lambda(rows: list[DailyBarSnapshot]) -> float:
    values: list[float] = []
    for row in rows:
        amount = float(row.amount or 0.0)
        pct_chg = abs(float(row.pct_chg or 0.0)) / 100.0
        if amount > 0 and pct_chg > 0:
            values.append(pct_chg / amount)
    return round(_safe_mean(values), 14)


def _impact_rate(participation: float, params: dict[str, Any]) -> float:
    thresholds = _float_list(params.get("market_impact_participation_thresholds"), [0.02, 0.05, 0.10])
    rates = _float_list(params.get("market_impact_rates"), [0.0008, 0.0015, 0.003, 0.008])
    for index, threshold in enumerate(thresholds):
        if participation <= threshold:
            return rates[min(index, len(rates) - 1)]
    return rates[-1] if rates else 0.008


def _slippage_pct(params: dict[str, Any]) -> float:
    bps = float(params.get("paper_slippage_stock_bps") or 5.0)
    return bps / 100.0


def _float_list(value: Any, fallback: list[float]) -> list[float]:
    if not isinstance(value, list):
        return fallback
    result: list[float] = []
    for item in value:
        try:
            result.append(float(item))
        except (TypeError, ValueError):
            continue
    return result or fallback


def _safe_mean(values: list[float]) -> float:
    cleaned = [float(item) for item in values if item is not None]
    return float(mean(cleaned)) if cleaned else 0.0


def _now_text() -> str:
    from datetime import datetime

    return datetime.utcnow().isoformat(timespec="seconds")
