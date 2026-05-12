from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.entities import PaperAccount
from app.services.market_data import MarketDataService
from app.services.paper.dynamic_exit import evaluate_paper_exit
from app.services.paper.position import PaperPositionService
from app.services.paper.quote_quality import PaperQuotePrice
from app.services.paper.scheduler_helpers import (
    _beijing_now_naive,
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
        quote = prices.get(row.symbol)
        if quote is None or not quote.usable:
            logger.warning(
                "自动退出计划跳过：%s 行情质量不可用 quality=%s，拒绝使用持仓旧价兜底 account_id=%s",
                row.symbol,
                getattr(quote, "quality", "missing"),
                account.id,
            )
            skipped_symbols.append(row.symbol)
            continue
        price = quote.price
        decision = evaluate_paper_exit(row, price=price, now=now)
        if decision.quantity <= 0:
            continue
        reason = decision.reason
        strategy_key = decision.strategy_key or _primary_strategy_from_position(row) or "paper_exit_plan"
        orders.append(
            {
                "symbol": row.symbol,
                "name": row.name or row.symbol,
                "side": "sell",
                "order_type": "market",
                "quantity": decision.quantity,
                "price": price,
                "current_price": price,
                "quote_time": now,
                "source": "auto_exit",
                "strategy_key": strategy_key,
                "reason": reason,
                "signal_snapshot": {
                    "exit_reason": reason,
                    "exit_code": decision.code,
                    "pnl_pct": decision.pnl_pct,
                    "hold_days": decision.hold_days,
                    "sell_ratio": decision.sell_ratio,
                    "cost_basis": float(row.cost_basis or 0),
                    "strategy_key": strategy_key,
                    "dynamic_exit": True,
                },
            }
        )
    reason = EXIT_QUOTES_UNAVAILABLE_REASON if skipped_symbols and not orders else ""
    return orders, reason


def latest_prices(symbols: list[str]) -> dict[str, PaperQuotePrice]:
    try:
        quotes = MarketDataService().get_quotes_batch(symbols)
    except Exception:
        logger.warning("自动退出计划批量行情失败，本轮不生成自动退出委托", exc_info=True)
        return {}
    result: dict[str, PaperQuotePrice] = {}
    for symbol, quote in quotes.items():
        price = float(getattr(quote, "last_price", 0) or 0)
        quality = "stale" if bool(getattr(quote, "is_stale", False)) else "fresh"
        if price <= 0:
            quality = "unavailable"
        result[symbol] = PaperQuotePrice(
            symbol=symbol,
            price=price,
            quality=quality,
            source=str(getattr(quote, "data_source", "") or ""),
            message=str(getattr(quote, "source_quality", "") or ""),
        )
    return result
