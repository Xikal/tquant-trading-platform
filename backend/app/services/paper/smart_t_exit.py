from __future__ import annotations

import json
import logging
from datetime import datetime, time
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import PaperAccount, PaperOrder, PaperPosition
from app.services.paper.fees import calculate_fee
from app.services.paper.quote_quality import PaperQuotePrice
from app.services.paper.smart_exit_context import PaperExitContext

logger = logging.getLogger(__name__)


def build_smart_t_exit_orders(
    *,
    db: Session,
    account: PaperAccount,
    positions: list[PaperPosition],
    prices: dict[str, PaperQuotePrice],
    contexts: dict[str, PaperExitContext],
    params: dict[str, Any],
    now: datetime,
    used_order_count: int,
    max_orders: int,
    market_state: str = "",
) -> list[dict[str, Any]]:
    if used_order_count >= max_orders:
        return []
    position_by_symbol = {row.symbol: row for row in positions}
    exited_order_ids = _today_exited_order_ids(db, account.id, now)
    orders: list[dict[str, Any]] = []
    for buy_order in _today_smart_t_buys(db, account.id, now):
        if len(orders) + used_order_count >= max_orders:
            break
        if buy_order.id in exited_order_ids:
            continue
        row = position_by_symbol.get(buy_order.symbol)
        quote = prices.get(buy_order.symbol)
        if row is None or quote is None or not quote.usable:
            continue
        quantity = min(int(buy_order.filled_quantity or buy_order.quantity or 0), int(row.available_quantity or 0))
        if quantity <= 0:
            continue
        plan = _exit_plan(
            buy_order=buy_order,
            row=row,
            quote=quote,
            context=contexts.get(buy_order.symbol),
            params=params,
            now=now,
            quantity=quantity,
            market_state=market_state,
        )
        if plan:
            orders.append(plan)
    return orders


def _exit_plan(
    *,
    buy_order: PaperOrder,
    row: PaperPosition,
    quote: PaperQuotePrice,
    context: PaperExitContext | None,
    params: dict[str, Any],
    now: datetime,
    quantity: int,
    market_state: str,
) -> dict[str, Any] | None:
    entry = _entry_price(buy_order)
    if entry <= 0 or quote.price <= 0:
        return None
    expected_rebound = _expected_rebound_pct(params=params, market_state=market_state)
    stop_loss = _float_param(params, "smart_t_exit_stop_loss_pct", -0.6)
    elapsed = _elapsed_minutes(buy_order.created_at, now)
    target_price = entry * (1 + expected_rebound / 100)
    stop_price = entry * (1 + stop_loss / 100)
    reason_code = ""
    reason_text = ""
    if quote.price >= target_price and _net_edge_ok(symbol=row.symbol, entry=entry, price=quote.price, quantity=quantity):
        reason_code = "smart_t_take_profit"
        reason_text = "T仓触达预设止盈价，优先兑现日内差价"
    elif quote.price <= stop_price:
        reason_code = "smart_t_stop_loss"
        reason_text = "T仓买入后继续下跌，按做T止损退出"
    elif elapsed >= int(_float_param(params, "smart_t_exit_time_minutes", 60)):
        reason_code = "smart_t_time_stop"
        reason_text = "T仓超过时间窗口未兑现，避免隔夜风险"
    elif context and context.high_pullback_ratio >= _float_param(params, "smart_t_high_pullback_exit_ratio", 0.5):
        reason_code = "smart_t_high_pullback"
        reason_text = "冲高后回落过半，优先卖出可卖底仓锁定差价"
    if not reason_code:
        return None
    snapshot = {
        "smart_t_action": "positive_t_exit",
        "smart_t_source_order_id": buy_order.id,
        "entry_price": round(entry, 4),
        "target_price": round(target_price, 4),
        "stop_price": round(stop_price, 4),
        "elapsed_minutes": elapsed,
        "exit_code": reason_code,
        "market_state": market_state,
        "high_pullback_ratio": getattr(context, "high_pullback_ratio", 0.0) if context else 0.0,
    }
    return {
        "symbol": row.symbol,
        "name": row.name or row.symbol,
        "side": "sell",
        "order_type": "market",
        "quantity": quantity,
        "price": quote.price,
        "current_price": quote.price,
        "quote_time": now,
        "source": "auto_smart_t_exit",
        "strategy_key": "smart_positive_t_exit",
        "reason": reason_text,
        "signal_snapshot": snapshot,
        "require_intraday_confirmation": False,
    }


def _today_smart_t_buys(db: Session, account_id: int, now: datetime) -> list[PaperOrder]:
    start = datetime.combine(now.date(), time.min)
    return list(
        db.execute(
            select(PaperOrder)
            .where(
                PaperOrder.account_id == account_id,
                PaperOrder.source == "auto_smart_t",
                PaperOrder.side == "buy",
                PaperOrder.status == "filled",
                PaperOrder.created_at >= start,
            )
            .order_by(PaperOrder.id.asc())
        ).scalars()
    )


def _today_exited_order_ids(db: Session, account_id: int, now: datetime) -> set[int]:
    start = datetime.combine(now.date(), time.min)
    ids: set[int] = set()
    rows = db.execute(
        select(PaperOrder.signal_snapshot)
        .where(
            PaperOrder.account_id == account_id,
            PaperOrder.source == "auto_smart_t_exit",
            PaperOrder.side == "sell",
            PaperOrder.created_at >= start,
        )
    ).scalars()
    for raw in rows:
        try:
            payload = json.loads(raw or "{}")
        except Exception:
            logger.debug("SmartT exit snapshot parse failed", exc_info=True)
            continue
        source_id = payload.get("smart_t_source_order_id")
        if source_id:
            ids.add(int(source_id))
    return ids


def _entry_price(order: PaperOrder) -> float:
    raw = order.avg_fill_price if order.avg_fill_price is not None else order.price
    try:
        return float(raw or 0)
    except (TypeError, ValueError):
        return 0.0


def _elapsed_minutes(created_at: datetime | None, now: datetime) -> int:
    if created_at is None:
        return 0
    return max(0, int((now - created_at.replace(tzinfo=None)).total_seconds() // 60))


def _expected_rebound_pct(*, params: dict[str, Any], market_state: str) -> float:
    by_state = params.get("smart_t_expected_rebound_by_state")
    if isinstance(by_state, dict) and market_state in by_state:
        try:
            return float(by_state[market_state])
        except (TypeError, ValueError):
            pass
    return _float_param(params, "smart_t_expected_rebound_pct", 1.2)


def _net_edge_ok(*, symbol: str, entry: float, price: float, quantity: int) -> bool:
    buy_fee = calculate_fee(symbol=symbol, side="buy", price=Decimal(str(entry)), quantity=quantity)
    sell_fee = calculate_fee(symbol=symbol, side="sell", price=Decimal(str(price)), quantity=quantity)
    gross = entry * quantity
    return gross > 0 and (price - entry) * quantity > float(buy_fee.total_fee + sell_fee.total_fee)


def _float_param(params: dict[str, Any], key: str, fallback: float) -> float:
    try:
        return float(params.get(key, fallback))
    except (TypeError, ValueError):
        return float(fallback)
