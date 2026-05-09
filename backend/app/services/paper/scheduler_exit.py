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


def build_exit_orders(*, db: Session, account: PaperAccount) -> list[dict[str, Any]]:
    positions = PaperPositionService(db).get_positions(account.id)
    if not positions:
        return []
    prices = latest_prices([row.symbol for row in positions])
    orders: list[dict[str, Any]] = []
    now = _beijing_now_naive()
    for row in positions:
        price = prices.get(row.symbol) or float(row.latest_price or 0)
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
    return orders


def latest_prices(symbols: list[str]) -> dict[str, float]:
    try:
        quotes = MarketDataService().get_quotes_batch(symbols)
    except Exception:
        logger.warning("自动退出计划批量行情失败，回退持仓最新价", exc_info=True)
        return {}
    return {symbol: float(quote.last_price or 0) for symbol, quote in quotes.items() if float(quote.last_price or 0) > 0}
