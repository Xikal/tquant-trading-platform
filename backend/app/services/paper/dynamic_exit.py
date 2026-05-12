from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from math import floor
from typing import Any

from app.models.entities import PaperPosition
from app.services.low_buy.holding_policy import strategy_holding_policy
from app.services.low_buy.strategy_parameter_defaults_parts.runtime import PAPER_DYNAMIC_EXIT_DEFAULTS
from app.services.market.parameter_defaults import MARKET_SECTOR_ETF_T0_DEFAULTS
from app.services.quant.runtime_parameters import get_market_sector_etf_t0, get_paper_dynamic_exit


@dataclass(frozen=True)
class PaperExitDecision:
    quantity: int
    reason: str
    code: str
    pnl_pct: float
    hold_days: int
    sell_ratio: float
    strategy_key: str


def evaluate_paper_exit(row: PaperPosition, *, price: float, now: datetime) -> PaperExitDecision:
    available = int(row.available_quantity or 0)
    strategy_key = primary_strategy_from_position(row)
    cost = float(row.cost_basis or 0)
    hold_days = max((now - row.opened_at).days, 0) if row.opened_at else 0
    if available < 100 or price <= 0 or cost <= 0:
        return _no_exit(strategy_key=strategy_key, hold_days=hold_days)
    pnl_pct = (price - cost) / cost * 100
    if strategy_key == "sector_etf_t0":
        return _evaluate_sector_etf_exit(
            available=available,
            pnl_pct=pnl_pct,
            hold_days=hold_days,
            strategy_key=strategy_key,
        )
    return _evaluate_stock_exit(
        row=row,
        available=available,
        pnl_pct=pnl_pct,
        hold_days=hold_days,
        strategy_key=strategy_key,
    )


def primary_strategy_from_position(row: PaperPosition) -> str:
    try:
        values = json.loads(row.strategy_sources or "[]")
    except Exception:
        values = []
    if isinstance(values, list) and values:
        return str(values[0] or "")
    if isinstance(values, str):
        return values
    return ""


def _evaluate_sector_etf_exit(
    *,
    available: int,
    pnl_pct: float,
    hold_days: int,
    strategy_key: str,
) -> PaperExitDecision:
    params = _sector_etf_t0_params()
    take_profit = _float_param(params, "paper_auto_take_profit_pct", 1.2)
    stop_loss = _float_param(params, "paper_auto_stop_loss_pct", -0.8)
    time_min = _float_param(params, "paper_auto_time_exit_min_pct", 0.4)
    if pnl_pct >= take_profit:
        return _decision(
            available,
            ratio=1.0,
            pnl_pct=pnl_pct,
            hold_days=hold_days,
            strategy_key=strategy_key,
            code="etf_take_profit",
            reason=f"ETF T+0 自动止盈：浮盈{pnl_pct:.2f}%，兑现板块价差",
        )
    if pnl_pct <= stop_loss:
        return _decision(
            available,
            ratio=1.0,
            pnl_pct=pnl_pct,
            hold_days=hold_days,
            strategy_key=strategy_key,
            code="etf_stop_loss",
            reason=f"ETF T+0 自动止损：浮亏{pnl_pct:.2f}%，停止试错",
        )
    if hold_days >= 1 and pnl_pct < time_min:
        return _decision(
            available,
            ratio=1.0,
            pnl_pct=pnl_pct,
            hold_days=hold_days,
            strategy_key=strategy_key,
            code="etf_time_exit",
            reason="ETF T+0 时间退出：隔日未达价差目标，先退出",
        )
    return _no_exit(strategy_key=strategy_key, pnl_pct=pnl_pct, hold_days=hold_days)


def _evaluate_stock_exit(
    *,
    row: PaperPosition,
    available: int,
    pnl_pct: float,
    hold_days: int,
    strategy_key: str,
) -> PaperExitDecision:
    params = _stock_dynamic_params()
    hard_stop = _float_param(params, "hard_stop_loss_pct", -3.0)
    if pnl_pct <= hard_stop:
        return _decision(
            available,
            ratio=1.0,
            pnl_pct=pnl_pct,
            hold_days=hold_days,
            strategy_key=strategy_key,
            code="hard_stop_loss",
            reason=f"动态止损：浮亏{pnl_pct:.2f}%，跌破模拟止损线，先退出",
        )
    if _time_stop_triggered(row, pnl_pct=pnl_pct, hold_days=hold_days, params=params):
        policy = strategy_holding_policy(strategy_key)
        return _decision(
            available,
            ratio=1.0,
            pnl_pct=pnl_pct,
            hold_days=hold_days,
            strategy_key=strategy_key,
            code="time_exit",
            reason=f"时间退出：已持有{hold_days}天，超过{policy.brief}验证窗口，未达转强要求",
        )
    weak_days = int(_float_param(params, "weak_hold_exit_days", 3))
    weak_pct = _float_param(params, "weak_hold_exit_pct", 0.0)
    if hold_days >= weak_days and pnl_pct < weak_pct:
        return _decision(
            available,
            ratio=1.0,
            pnl_pct=pnl_pct,
            hold_days=hold_days,
            strategy_key=strategy_key,
            code="weak_hold_exit",
            reason=f"动态退出：持有{hold_days}天仍未转强，避免资金继续占用",
        )
    strong_pct = _float_param(params, "strong_take_profit_pct", 8.0)
    if pnl_pct >= strong_pct:
        ratio = _float_param(params, "strong_take_profit_sell_ratio", 1.0)
        return _decision(
            available,
            ratio=ratio,
            pnl_pct=pnl_pct,
            hold_days=hold_days,
            strategy_key=strategy_key,
            code="strong_take_profit",
            reason=f"动态止盈：浮盈{pnl_pct:.2f}%，进入高收益区，优先锁定利润",
        )
    take_profit = _float_param(params, "take_profit_pct", 5.0)
    if pnl_pct >= take_profit:
        ratio = _float_param(params, "take_profit_sell_ratio", 0.7)
        return _decision(
            available,
            ratio=ratio,
            pnl_pct=pnl_pct,
            hold_days=hold_days,
            strategy_key=strategy_key,
            code="take_profit",
            reason=f"动态止盈：浮盈{pnl_pct:.2f}%，先兑现大部分仓位，防止利润回吐",
        )
    protect_pct = _float_param(params, "protect_profit_trigger_pct", 3.0)
    wash_buffer = _float_param(params, "wash_buffer_profit_pct", 1.2)
    if hold_days >= 1 and pnl_pct >= protect_pct:
        ratio = _float_param(params, "protect_profit_sell_ratio", 0.5)
        return _decision(
            available,
            ratio=ratio,
            pnl_pct=pnl_pct,
            hold_days=hold_days,
            strategy_key=strategy_key,
            code="profit_protection",
            reason=f"利润保护：浮盈{pnl_pct:.2f}%，先减半锁定收益，剩余仓位观察承接",
        )
    if pnl_pct >= wash_buffer:
        return _no_exit(strategy_key=strategy_key, pnl_pct=pnl_pct, hold_days=hold_days)
    return _no_exit(strategy_key=strategy_key, pnl_pct=pnl_pct, hold_days=hold_days)


def _time_stop_triggered(row: PaperPosition, *, pnl_pct: float, hold_days: int, params: dict[str, Any]) -> bool:
    policy = strategy_holding_policy(primary_strategy_from_position(row))
    if hold_days < int(policy.max_holding_days):
        return False
    return pnl_pct < _float_param(params, "time_exit_min_return_pct", 2.0)


def _decision(
    available: int,
    *,
    ratio: float,
    pnl_pct: float,
    hold_days: int,
    strategy_key: str,
    code: str,
    reason: str,
) -> PaperExitDecision:
    quantity = _round_lot(max(100, floor(available * max(min(ratio, 1.0), 0.0))))
    return PaperExitDecision(
        quantity=quantity,
        reason=reason,
        code=code,
        pnl_pct=round(pnl_pct, 4),
        hold_days=hold_days,
        sell_ratio=round(max(min(ratio, 1.0), 0.0), 4),
        strategy_key=strategy_key,
    )


def _no_exit(*, strategy_key: str, pnl_pct: float = 0.0, hold_days: int = 0) -> PaperExitDecision:
    return PaperExitDecision(
        quantity=0,
        reason="",
        code="hold",
        pnl_pct=round(pnl_pct, 4),
        hold_days=hold_days,
        sell_ratio=0.0,
        strategy_key=strategy_key,
    )


def _round_lot(quantity: int | float) -> int:
    return int(floor(float(quantity) / 100) * 100)


def _stock_dynamic_params() -> dict[str, Any]:
    values = get_paper_dynamic_exit()
    if isinstance(values, dict):
        return {**PAPER_DYNAMIC_EXIT_DEFAULTS, **values}
    return dict(PAPER_DYNAMIC_EXIT_DEFAULTS)


def _sector_etf_t0_params() -> dict[str, Any]:
    values = get_market_sector_etf_t0()
    if isinstance(values, dict):
        return {**MARKET_SECTOR_ETF_T0_DEFAULTS, **values}
    return dict(MARKET_SECTOR_ETF_T0_DEFAULTS)


def _float_param(params: dict[str, Any], key: str, fallback: float) -> float:
    try:
        return float(params.get(key, fallback))
    except (TypeError, ValueError):
        return float(fallback)
