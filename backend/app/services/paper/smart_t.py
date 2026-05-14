from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, time
from decimal import Decimal
from math import floor
from typing import Any

from app.models.entities import PaperAccount, PaperPosition
from app.services.paper.dynamic_exit import evaluate_paper_exit, primary_strategy_from_position
from app.services.paper.fees import calculate_fee
from app.services.paper.quote_quality import PaperQuotePrice
from app.services.paper.smart_exit_context import PaperExitContext

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SmartTAddPlan:
    symbol: str
    name: str
    quantity: int
    price: float
    reason: str
    signal_snapshot: dict[str, Any]

    def to_order(self, *, now: datetime) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "side": "buy",
            "order_type": "market",
            "quantity": self.quantity,
            "price": self.price,
            "current_price": self.price,
            "quote_time": now,
            "source": "auto_smart_t",
            "strategy_key": "smart_positive_t",
            "reason": self.reason,
            "signal_snapshot": self.signal_snapshot,
            "require_intraday_confirmation": False,
        }


def build_smart_t_add_orders(
    *,
    account: PaperAccount,
    positions: list[PaperPosition],
    prices: dict[str, PaperQuotePrice],
    contexts: dict[str, PaperExitContext],
    today_orders: list[dict[str, Any]],
    params: dict[str, Any],
    now: datetime,
    used_order_count: int,
    max_orders: int,
    market_state: str = "",
) -> list[dict[str, Any]]:
    if not _bool_param(params, "smart_t_add_enabled", True) or used_order_count >= max_orders:
        return []
    if not _market_state_allows_add(params, market_state) or not _time_allows_add(params, now):
        return []
    today_buy_symbols = _today_buy_symbols(today_orders)
    plans: list[SmartTAddPlan] = []
    remaining_cash = float(account.cash_available or 0)
    total_assets = max(float(account.total_assets or 0), 1.0)
    symbol_cap = max(1, int(_float_param(params, "smart_t_max_symbols_per_cycle", 1)))
    for row in positions:
        if len(plans) + used_order_count >= max_orders or len(plans) >= symbol_cap:
            break
        quote = prices.get(row.symbol)
        context = contexts.get(row.symbol)
        if quote is None or context is None or not quote.usable or row.symbol in today_buy_symbols:
            continue
        if int(row.available_quantity or 0) < int(_float_param(params, "smart_t_min_available_base", 100)):
            continue
        try:
            decision = evaluate_paper_exit(row, price=quote.price, now=now, context=context)
        except Exception as exc:
            logger.warning("SmartT position %s eval failed: %s", row.symbol, exc)
            continue
        if decision.action_signal != "washout":
            continue
        if not _context_allows_add(row=row, quote=quote, context=context, params=params):
            continue
        plan = _size_add_plan(
            row=row,
            account=account,
            quote=quote,
            context=context,
            decision=decision,
            remaining_cash=remaining_cash,
            total_assets=total_assets,
            params=params,
            market_state=market_state,
        )
        if plan is None:
            continue
        plans.append(plan)
        remaining_cash -= plan.quantity * plan.price
        if remaining_cash <= 0:
            break
    return [plan.to_order(now=now) for plan in plans]


def _size_add_plan(
    *,
    row: PaperPosition,
    account: PaperAccount,
    quote: PaperQuotePrice,
    context: PaperExitContext,
    decision,
    remaining_cash: float,
    total_assets: float,
    params: dict[str, Any],
    market_state: str,
) -> SmartTAddPlan | None:
    current_position_value = float(row.market_value or 0)
    max_position_pct = _float_param(params, "smart_t_add_max_position_pct", 0.25)
    cash_pct = _cash_pct_for_account(account=account, row=row, params=params)
    max_position_value = total_assets * max_position_pct - current_position_value
    max_cash_value = min(remaining_cash, total_assets * cash_pct)
    order_value = min(max_position_value, max_cash_value)
    if order_value <= 0 or quote.price <= 0:
        return None
    quantity = _round_lot(order_value / quote.price)
    if quantity < 100:
        return None
    expected_rebound = _expected_rebound_pct(params=params, market_state=market_state)
    if not _expected_net_edge_ok(
        symbol=row.symbol,
        price=quote.price,
        quantity=quantity,
        expected_rebound=expected_rebound,
        params=params,
    ):
        return None
    strategy_key = primary_strategy_from_position(row)
    snapshot = {
        "smart_t_action": "positive_t_add",
        "source_position_strategy": strategy_key,
        "base_available_quantity": int(row.available_quantity or 0),
        "cost_basis": float(row.cost_basis or 0),
        "vwap": context.vwap,
        "volume_release_ratio": context.volume_release_ratio,
        "volume_usable": context.volume_usable,
        "pnl_pct": decision.pnl_pct,
        "market_state": market_state,
        "expected_rebound_pct": expected_rebound,
        "entry_gate": "缩量低点不破，且价格低于分时均价线",
        "invalid_condition": "加仓后不能继续放量跌破分时均价线；冲高优先卖出可卖底仓。",
        "failure_action": "若加仓后没有反抽，下一轮按硬止损或时间退出处理。",
    }
    return SmartTAddPlan(
        symbol=row.symbol,
        name=row.name or row.symbol,
        quantity=quantity,
        price=quote.price,
        reason=f"智能做T加仓：疑似缩量洗盘后承接恢复，小仓加仓 {quantity} 股，冲高优先卖出底仓",
        signal_snapshot=snapshot,
    )


def _expected_net_edge_ok(
    *,
    symbol: str,
    price: float,
    quantity: int,
    expected_rebound: float,
    params: dict[str, Any],
) -> bool:
    min_net = _float_param(params, "min_net_profit_pct", 0.6)
    buy_fee = calculate_fee(symbol=symbol, side="buy", price=Decimal(str(price)), quantity=quantity)
    sell_price = price * (1 + expected_rebound / 100)
    sell_fee = calculate_fee(symbol=symbol, side="sell", price=Decimal(str(sell_price)), quantity=quantity)
    gross = price * quantity
    fee_drag_pct = (float(buy_fee.total_fee + sell_fee.total_fee) / gross * 100) if gross > 0 else 0.0
    return expected_rebound - fee_drag_pct >= min_net


def _context_allows_add(
    *,
    row: PaperPosition,
    quote: PaperQuotePrice,
    context: PaperExitContext,
    params: dict[str, Any],
) -> bool:
    if _bool_param(params, "smart_t_profitable_position_only", True):
        if _float_attr(row, "unrealized_pnl_pct") < _float_param(params, "smart_t_profit_position_pnl_floor_pct", 0.0):
            return False
    if not context.volume_usable:
        return False
    if context.volume_release_ratio > _float_param(params, "smart_t_add_volume_ratio_max", 0.4):
        return False
    if _bool_param(params, "smart_t_require_low_rising", True) and not context.low_rising:
        return False
    if not context.vwap or context.vwap <= 0:
        return False
    max_entry = context.vwap * (1 - _float_param(params, "smart_t_buy_below_vwap_pct", 0.3) / 100)
    return quote.price <= max_entry


def _market_state_allows_add(params: dict[str, Any], market_state: str) -> bool:
    allowed = params.get("smart_t_allowed_market_states") or ["broad_rally", "repair"]
    if not isinstance(allowed, list):
        allowed = ["broad_rally", "repair"]
    return str(market_state or "").strip() in {str(item) for item in allowed}


def _time_allows_add(params: dict[str, Any], now: datetime) -> bool:
    current = now.time()
    if not (time(9, 30) <= current <= time(15, 0)):
        return False
    open_avoid = int(_float_param(params, "smart_t_open_avoid_minutes", 30))
    close_avoid = int(_float_param(params, "smart_t_close_avoid_minutes", 30))
    minutes = current.hour * 60 + current.minute
    if minutes < 9 * 60 + 30 + open_avoid:
        return False
    if minutes >= 15 * 60 - close_avoid:
        return False
    return True


def _cash_pct_for_account(*, account: PaperAccount, row: PaperPosition, params: dict[str, Any]) -> float:
    account_pnl = float(getattr(account, "total_assets", 0) or 0) - float(getattr(account, "initial_cash", 0) or 0)
    if account_pnl >= 0 and _float_attr(row, "unrealized_pnl_pct") >= 0:
        return _float_param(params, "smart_t_add_cash_pct_profit", 0.12)
    if account_pnl < 0 or _float_attr(row, "unrealized_pnl_pct") < 0:
        return _float_param(params, "smart_t_add_cash_pct_loss", 0.04)
    return _float_param(params, "smart_t_add_cash_pct", 0.08)


def _expected_rebound_pct(*, params: dict[str, Any], market_state: str) -> float:
    by_state = params.get("smart_t_expected_rebound_by_state")
    if isinstance(by_state, dict) and market_state in by_state:
        try:
            return float(by_state[market_state])
        except (TypeError, ValueError):
            pass
    return _float_param(params, "smart_t_expected_rebound_pct", 1.2)


def _today_buy_symbols(rows: list[dict[str, Any]]) -> set[str]:
    return {
        str(row.get("symbol") or "").strip()
        for row in rows
        if str(row.get("side") or "") == "buy" and str(row.get("status") or "") in {"pending", "filled", "partial"}
    }


def _round_lot(quantity: float) -> int:
    return int(floor(quantity / 100) * 100)


def _float_param(params: dict[str, Any], key: str, fallback: float) -> float:
    try:
        return float(params.get(key, fallback))
    except (TypeError, ValueError):
        return float(fallback)


def _float_attr(row: PaperPosition, key: str) -> float:
    try:
        return float(getattr(row, key, 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def _bool_param(params: dict[str, Any], key: str, fallback: bool) -> bool:
    value = params.get(key, fallback)
    if isinstance(value, str):
        return value.lower() in {"1", "true", "yes", "on"}
    return bool(value)
