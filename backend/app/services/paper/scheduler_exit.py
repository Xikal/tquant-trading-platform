from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.entities import PaperAccount
from app.services.market_data import MarketDataService
from app.services.paper.position import PaperPositionService
from app.services.paper.scheduler_helpers import (
    _beijing_now_naive,
    _exit_quantity,
    _exit_reason,
    _primary_strategy_from_position,
)

logger = logging.getLogger(__name__)

EXIT_QUOTES_UNAVAILABLE_REASON = "自动退出暂停：行情数据不可用，等待下轮刷新。"


def build_exit_orders(*, db: Session, account: PaperAccount) -> list[dict[str, Any]]:
    orders, _reason = build_exit_order_plan(db=db, account=account)
    return orders


def build_exit_order_plan(*, db: Session, account: PaperAccount) -> tuple[list[dict[str, Any]], str]:
    positions = PaperPositionService(db).get_positions(account.id)
    if not positions:
        return [], ""
    prices = latest_prices([row.symbol for row in positions])
    if not prices:
        logger.warning("自动退出计划暂停：本轮批量行情不可用，拒绝使用持仓旧价兜底 account_id=%s", account.id)
        return [], EXIT_QUOTES_UNAVAILABLE_REASON
    orders: list[dict[str, Any]] = []
    skipped_symbols: list[str] = []
    now = _beijing_now_naive()
    for row in positions:
        price = prices.get(row.symbol)
        if price is None or price <= 0:
            logger.warning("自动退出计划跳过：%s 行情不可用，拒绝使用持仓旧价兜底 account_id=%s", row.symbol, account.id)
            skipped_symbols.append(row.symbol)
            continue
        quantity = _exit_quantity(row, price=price, now=now)
        if quantity <= 0:
            continue
        reason = _exit_reason(row, price=price, now=now)
        strategy_key = _primary_strategy_from_position(row) or "paper_exit_plan"
        orders.append(
            {
                "symbol": row.symbol,
                "name": row.name or row.symbol,
                "side": "sell",
                "order_type": "market",
                "quantity": quantity,
                "price": price,
                "current_price": price,
                "quote_time": now,
                "source": "auto_exit",
                "strategy_key": strategy_key,
                "reason": reason,
                "signal_snapshot": {
                    "exit_reason": reason,
                    "cost_basis": float(row.cost_basis or 0),
                    "strategy_key": strategy_key,
                },
            }
        )
    reason = EXIT_QUOTES_UNAVAILABLE_REASON if skipped_symbols and not orders else ""
    return orders, reason


def latest_prices(symbols: list[str]) -> dict[str, float]:
    try:
        quotes = MarketDataService().get_quotes_batch(symbols)
    except Exception:
        logger.warning("自动退出计划批量行情失败，本轮不生成自动退出委托", exc_info=True)
        return {}
    return {symbol: float(quote.last_price or 0) for symbol, quote in quotes.items() if float(quote.last_price or 0) > 0}
