from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from math import floor
from typing import Any

from app.models.entities import PaperPosition
from app.services.low_buy.holding_policy import strategy_holding_policy
from app.services.low_buy.strategy_parameter_defaults_parts.runtime import PAPER_DYNAMIC_EXIT_DEFAULTS
from app.services.market.parameter_defaults import MARKET_SECTOR_ETF_T0_DEFAULTS
from app.services.paper.exit_types import PaperExitActionSignal, PaperExitDecision
from app.services.paper.fees import calculate_fee
from app.services.paper.smart_exit_context import PaperExitContext
from app.services.paper.trailing_stop_decision import trailing_stop_decision
from app.services.quant.runtime_parameters import get_market_sector_etf_t0, get_paper_dynamic_exit


def evaluate_paper_exit(
    row: PaperPosition,
    *,
    price: float,
    now: datetime,
    context: PaperExitContext | None = None,
) -> PaperExitDecision:
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
        price=price,
        cost=cost,
        pnl_pct=pnl_pct,
        hold_days=hold_days,
        strategy_key=strategy_key,
        context=context,
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
            action_signal="profit_take",
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
            action_signal="hard_stop",
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
            action_signal="time_stop",
        )
    return _no_exit(strategy_key=strategy_key, pnl_pct=pnl_pct, hold_days=hold_days)


def _evaluate_stock_exit(
    *,
    row: PaperPosition,
    available: int,
    price: float,
    cost: float,
    pnl_pct: float,
    hold_days: int,
    strategy_key: str,
    context: PaperExitContext | None,
) -> PaperExitDecision:
    params = _stock_dynamic_params()
    hard_stop = _float_param(params, "hard_stop_loss_pct", -3.0)
    fee_drag_pct = _fee_drag_pct(symbol=row.symbol, price=price, quantity=available)
    net_profit_pct = pnl_pct - fee_drag_pct
    if _is_wash_pullback(pnl_pct=pnl_pct, context=context, params=params):
        return _no_exit(
            strategy_key=strategy_key,
            pnl_pct=pnl_pct,
            hold_days=hold_days,
            action_text="疑似洗盘，暂不止损",
            action_signal="washout",
            why=f"{_context_reason(context)}缩量回踩未破结构，等待重新站回分时均价线。",
            invalid_condition="放量跌破分时均价线或关键支撑时减仓。",
            failure_action="若重新站回分时均价线，可等系统小仓加仓；反抽后优先卖出可卖底仓做T。",
            fee_drag_pct=fee_drag_pct,
            net_profit_pct=net_profit_pct,
        )
    if pnl_pct <= hard_stop:
        return _decision(
            available,
            ratio=1.0,
            pnl_pct=pnl_pct,
            hold_days=hold_days,
            strategy_key=strategy_key,
            code="hard_stop_loss",
            reason=f"动态止损：浮亏{pnl_pct:.2f}%，跌破模拟止损线，先退出",
            action_signal="hard_stop",
            action_text="硬止损退出",
            why="浮亏已超过硬止损线，不能继续用补仓摊低风险。",
            invalid_condition="重新站回成本和分时均价线前不再加仓。",
            fee_drag_pct=fee_drag_pct,
            net_profit_pct=net_profit_pct,
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
            action_signal="time_stop",
            action_text="时间退出",
            why="持仓超过策略验证窗口仍未转强，资金效率下降。",
            invalid_condition="重新出现确定买入信号后再评估。",
            fee_drag_pct=fee_drag_pct,
            net_profit_pct=net_profit_pct,
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
            action_signal="time_stop",
            action_text="弱势退出",
            why="持仓多日未转强，且收益没有覆盖等待成本。",
            invalid_condition="重新放量站回分时均价线和策略关键位前不补仓。",
            fee_drag_pct=fee_drag_pct,
            net_profit_pct=net_profit_pct,
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
            action_signal="profit_take",
            action_text="强势大部分止盈",
            why="浮盈进入高收益区，先锁定利润，避免单日回吐。",
            invalid_condition="若继续放量创新高，剩余仓位跟随；跌破分时均价线则退出。",
            fee_drag_pct=fee_drag_pct,
            net_profit_pct=net_profit_pct,
        )
    if _no_volume_rally(pnl_pct=pnl_pct, context=context, params=params) and _net_profit_ok(net_profit_pct, params):
        ratio = _float_param(params, "no_volume_take_profit_sell_ratio", 0.35)
        return _decision(
            available,
            ratio=ratio,
            pnl_pct=pnl_pct,
            hold_days=hold_days,
            strategy_key=strategy_key,
            code="no_volume_take_profit",
            reason=f"冲高无量止盈：浮盈{pnl_pct:.2f}%，量能未释放，先分批兑现",
            action_signal="scale_out",
            action_text="冲高无量，分批止盈",
            why=f"{_context_reason(context)}预计净收益{net_profit_pct:.2f}%，已覆盖手续费。",
            invalid_condition="若重新放量站稳分时均价线，剩余仓位继续观察。",
            fee_drag_pct=fee_drag_pct,
            net_profit_pct=net_profit_pct,
        )
    trailing = trailing_stop_decision(
        available=available,
        price=price,
        pnl_pct=pnl_pct,
        hold_days=hold_days,
        strategy_key=strategy_key,
        context=context,
        params=params,
        fee_drag_pct=fee_drag_pct,
        net_profit_pct=net_profit_pct,
        make_decision=_decision,
        float_param=_float_param,
    )
    if trailing is not None:
        return trailing
    protect_pct = _float_param(params, "protect_profit_trigger_pct", 3.0)
    if (
        context is not None
        and context.intraday_usable
        and pnl_pct >= protect_pct
        and not context.above_vwap
        and _net_profit_ok(net_profit_pct, params)
    ):
        ratio = _float_param(params, "vwap_break_sell_ratio", 0.5)
        return _decision(
            available,
            ratio=ratio,
            pnl_pct=pnl_pct,
            hold_days=hold_days,
            strategy_key=strategy_key,
            code="vwap_break_profit_protection",
            reason=f"跌破分时均价线减仓：浮盈{pnl_pct:.2f}%，先保护利润",
            action_signal="scale_out",
            action_text="跌破分时均价线，保护利润",
            why=f"{_context_reason(context)}浮盈已达保护线，先卖出一部分。",
            invalid_condition="若重新放量站回分时均价线，剩余仓位继续观察。",
            fee_drag_pct=fee_drag_pct,
            net_profit_pct=net_profit_pct,
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
            action_signal="profit_take",
            action_text="常规分批止盈",
            why="收益已达常规止盈线，先兑现大部分仓位。",
            invalid_condition="剩余仓位跌破分时均价线或回吐过半时继续减仓。",
            fee_drag_pct=fee_drag_pct,
            net_profit_pct=net_profit_pct,
        )
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
            action_signal="scale_out",
            action_text="利润保护减仓",
            why=f"{_context_reason(context)}浮盈已进入保护区，避免利润回吐。",
            invalid_condition="剩余仓位跌破分时均价线或回吐过半时继续减仓。",
            fee_drag_pct=fee_drag_pct,
            net_profit_pct=net_profit_pct,
        )
    first_profit = _float_param(params, "first_take_profit_pct", 2.0)
    if pnl_pct >= first_profit and _net_profit_ok(net_profit_pct, params):
        ratio = _float_param(params, "first_take_profit_sell_ratio", 0.3)
        return _decision(
            available,
            ratio=ratio,
            pnl_pct=pnl_pct,
            hold_days=hold_days,
            strategy_key=strategy_key,
            code="first_take_profit",
            reason=f"第一档止盈：浮盈{pnl_pct:.2f}%，先小幅兑现，保留后续做T空间",
            action_signal="scale_out",
            action_text="第一档止盈",
            why=f"收益已覆盖手续费，预计净收益{net_profit_pct:.2f}%，先卖一部分降低回吐风险。",
            invalid_condition="若回落不破分时均价线，剩余仓位继续观察。",
            fee_drag_pct=fee_drag_pct,
            net_profit_pct=net_profit_pct,
        )
    if pnl_pct >= wash_buffer:
        return _no_exit(
            strategy_key=strategy_key,
            pnl_pct=pnl_pct,
            hold_days=hold_days,
            action_text="持有观察",
            why="仍有小幅浮盈，暂未触发分批止盈或风控退出。",
            invalid_condition="跌破分时均价线且放量转弱时减仓。",
            fee_drag_pct=fee_drag_pct,
            net_profit_pct=net_profit_pct,
        )
    return _no_exit(
        strategy_key=strategy_key,
        pnl_pct=pnl_pct,
        hold_days=hold_days,
        action_text="等待确认",
        why="当前收益和风险都未到自动处理阈值。",
        invalid_condition="跌破硬止损线直接退出；重新站回分时均价线后再评估加仓或做T。",
        fee_drag_pct=fee_drag_pct,
        net_profit_pct=net_profit_pct,
    )


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
    action_text: str = "自动退出",
    action_signal: PaperExitActionSignal = "profit_take",
    why: str = "",
    invalid_condition: str = "",
    failure_action: str = "",
    fee_drag_pct: float = 0.0,
    net_profit_pct: float = 0.0,
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
        action_signal=action_signal,
        action_text=action_text,
        why=why or reason,
        invalid_condition=invalid_condition,
        failure_action=failure_action,
        fee_drag_pct=round(fee_drag_pct, 4),
        net_profit_pct=round(net_profit_pct, 4),
    )


def _no_exit(
    *,
    strategy_key: str,
    pnl_pct: float = 0.0,
    hold_days: int = 0,
    action_text: str = "继续观察",
    action_signal: PaperExitActionSignal = "hold",
    why: str = "",
    invalid_condition: str = "",
    failure_action: str = "",
    fee_drag_pct: float = 0.0,
    net_profit_pct: float = 0.0,
) -> PaperExitDecision:
    return PaperExitDecision(
        quantity=0,
        reason=why,
        code="hold",
        pnl_pct=round(pnl_pct, 4),
        hold_days=hold_days,
        sell_ratio=0.0,
        strategy_key=strategy_key,
        action_signal=action_signal,
        action_text=action_text,
        why=why,
        invalid_condition=invalid_condition,
        failure_action=failure_action,
        fee_drag_pct=round(fee_drag_pct, 4),
        net_profit_pct=round(net_profit_pct, 4),
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


def _is_wash_pullback(*, pnl_pct: float, context: PaperExitContext | None, params: dict[str, Any]) -> bool:
    if context is None or not context.intraday_usable:
        return False
    if not context.volume_usable:
        return False
    if pnl_pct < _float_param(params, "wash_pullback_loss_floor_pct", -2.5):
        return False
    volume_ok = context.volume_release_ratio <= _float_param(params, "wash_volume_ratio_max", 0.85)
    structure_ok = context.reclaimed_vwap or context.vwap_hold or context.low_rising
    return volume_ok and structure_ok and not (context.high_pullback_ratio >= 0.7 and not context.above_vwap)


def _no_volume_rally(*, pnl_pct: float, context: PaperExitContext | None, params: dict[str, Any]) -> bool:
    if context is None or not context.intraday_usable:
        return False
    if not context.volume_usable:
        return False
    if pnl_pct < _float_param(params, "no_volume_take_profit_pct", 2.0):
        return False
    volume_weak = context.volume_release_ratio <= _float_param(params, "no_volume_release_ratio", 0.8)
    pullback = context.high_pullback_ratio >= _float_param(params, "high_pullback_ratio", 0.45)
    vwap_lost = not context.above_vwap and context.high_pullback_pct >= 0.6
    return volume_weak and (pullback or vwap_lost)


def _net_profit_ok(net_profit_pct: float, params: dict[str, Any]) -> bool:
    return net_profit_pct >= _float_param(params, "min_net_profit_pct", 0.6)


def _fee_drag_pct(*, symbol: str, price: float, quantity: int) -> float:
    if price <= 0 or quantity <= 0:
        return 0.0
    detail = calculate_fee(symbol=symbol, side="sell", price=Decimal(str(price)), quantity=quantity)
    gross = float(detail.gross_amount or 0)
    return float(detail.total_fee or 0) / gross * 100 if gross > 0 else 0.0


def _context_reason(context: PaperExitContext | None) -> str:
    if context is None or not context.intraday_usable:
        return "分时量能不足，"
    return f"{context.reason} "
