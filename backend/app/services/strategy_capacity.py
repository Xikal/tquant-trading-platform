from __future__ import annotations

import math
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
from app.services.quant.runtime_parameters import get_backtest_execution, get_capacity_analysis


class StrategyCapacityService:
    """Estimate strategy capacity under liquidity and market-impact assumptions."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def evaluate(self, payload: StrategyCapacityRequest) -> StrategyCapacityResponse:
        strategies = payload.strategies or self._default_strategies()
        params = {**get_backtest_execution(), **get_capacity_analysis()}
        items = [
            self._evaluate_strategy(strategy_key=strategy, payload=payload, params=params)
            for strategy in strategies
        ]
        return StrategyCapacityResponse(
            generated_at=_now_text(),
            capital_levels=payload.capital_levels,
            items=items,
            assumptions={
                "impact_model": "Square-root market impact + participation tier",
                "capital_levels": payload.capital_levels,
                "start_date": payload.start_date,
                "end_date": payload.end_date,
                "formula": "impact_pct = eta * realized_volatility_pct * sqrt(order_amount / average_daily_amount)",
                "notes": [
                    "容量评估只用于资金规模约束，不构成交易承诺。",
                    "平方根冲击模型使用近似订单金额/平均成交额的参与度估算，避免 Kyle Lambda 量纲误用。",
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
        volatility_pct = _realized_volatility_pct(bars, params)
        base_edge_pct = _safe_mean([float(row.pnl_pct or 0.0) for row in trades])
        lambda_value = _kyle_lambda(bars)
        slippage_pct = _slippage_pct(params)
        curve = [
            _capacity_point(
                capital=float(capital),
                avg_daily_amount=avg_daily_amount,
                volatility_pct=volatility_pct,
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
        elif avg_daily_amount < _float_param(params, "min_avg_amount", 100_000_000.0):
            notes.append("平均成交额低于容量分析建议阈值，容量结论需按保守口径使用。")
        if lambda_value <= 0:
            notes.append("Kyle Lambda 仅作诊断字段；生产容量冲击使用平方根模型与参与度分层。")
        return StrategyCapacityItem(
            strategy_key=strategy_key,
            sample_count=len(trades),
            symbol_count=len(symbols),
            avg_daily_amount=round(avg_daily_amount, 2),
            volatility_pct=round(volatility_pct, 4),
            base_edge_pct=round(base_edge_pct, 4),
            kyle_lambda=lambda_value,
            impact_model="sqrt_market_impact",
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
    volatility_pct: float,
    base_edge_pct: float,
    lambda_value: float,
    slippage_pct: float,
    params: dict[str, Any],
) -> StrategyCapacityPoint:
    participation = capital / avg_daily_amount if avg_daily_amount > 0 else 1.0
    kyle_impact_pct = max(lambda_value * capital * 100.0, 0.0)
    sqrt_impact_pct = _sqrt_impact_pct(
        capital=capital,
        avg_daily_amount=avg_daily_amount,
        volatility_pct=volatility_pct,
        params=params,
    )
    tier_impact_pct = _impact_rate(participation, params) * 100.0
    impact_pct = max(sqrt_impact_pct, tier_impact_pct)
    net_edge_pct = base_edge_pct - impact_pct - slippage_pct
    if avg_daily_amount <= 0 or participation >= 0.10 or net_edge_pct < 0:
        status = "过载"
    elif participation >= 0.05:
        status = "谨慎"
    else:
        status = "可承载"
    return StrategyCapacityPoint(
        capital=round(capital, 2),
        order_amount=round(capital, 2),
        participation_pct=round(participation * 100.0, 4),
        expected_edge_pct=round(base_edge_pct, 4),
        impact_model="sqrt_market_impact",
        impact_assumption=(
            "平方根冲击 + 参与度分层；Kyle Lambda 仅保留为诊断字段，不参与最终冲击成本。"
        ),
        average_daily_amount=round(avg_daily_amount, 2),
        volatility_pct=round(volatility_pct, 4),
        kyle_impact_pct=round(kyle_impact_pct, 4),
        impact_pct=round(impact_pct, 4),
        impact_cost_pct=round(impact_pct, 4),
        slippage_cost_pct=round(slippage_pct, 4),
        net_edge_pct=round(net_edge_pct, 4),
        capacity_status=status,
    )


def _sqrt_impact_pct(*, capital: float, avg_daily_amount: float, volatility_pct: float, params: dict[str, Any]) -> float:
    if avg_daily_amount <= 0:
        return _float_param(params, "max_impact_pct", _float_param(params, "capacity_max_impact_pct", 8.0))
    eta = max(_float_param(params, "impact_eta", _float_param(params, "capacity_impact_eta", 0.50)), 0.0)
    max_impact_pct = max(_float_param(params, "max_impact_pct", _float_param(params, "capacity_max_impact_pct", 8.0)), 0.0)
    participation = max(capital / avg_daily_amount, 0.0)
    impact_pct = eta * max(volatility_pct, 0.0) * math.sqrt(participation)
    return min(max(impact_pct, 0.0), max_impact_pct)


def _kyle_lambda(rows: list[DailyBarSnapshot]) -> float:
    values: list[float] = []
    for row in rows:
        amount = float(row.amount or 0.0)
        pct_chg = abs(float(row.pct_chg or 0.0)) / 100.0
        if amount > 0 and pct_chg > 0:
            values.append(pct_chg / amount)
    return round(_safe_mean(values), 14)


def _realized_volatility_pct(rows: list[DailyBarSnapshot], params: dict[str, Any]) -> float:
    values = [float(row.pct_chg or 0.0) for row in rows if row.pct_chg is not None]
    if len(values) < 2:
        return _float_param(params, "default_volatility_pct", _float_param(params, "capacity_default_volatility_pct", 2.0))
    avg_value = _safe_mean(values)
    variance = _safe_mean([(value - avg_value) ** 2 for value in values])
    return math.sqrt(max(variance, 0.0))


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


def _float_param(params: dict[str, Any], key: str, fallback: float) -> float:
    try:
        return float(params.get(key, fallback))
    except (TypeError, ValueError):
        return fallback


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
