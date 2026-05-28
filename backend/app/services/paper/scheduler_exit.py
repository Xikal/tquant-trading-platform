from __future__ import annotations

import logging
from dataclasses import replace
from typing import Any

from sqlalchemy.orm import Session

from app.models.entities import PaperAccount
from app.services.market_data import MarketDataService
from app.services.paper.dynamic_exit import evaluate_paper_exit
from app.services.paper.exit_model_advisor import ExitModelAdvisor
from app.services.paper.exit_model_features import build_exit_model_features
from app.services.paper.exit_model_schema import ExitModelShadowRecord
from app.services.paper.exit_model_shadow import record_exit_model_shadow
from app.services.paper.position import PaperPositionService
from app.services.paper.quote_quality import PaperQuotePrice
from app.services.paper.scheduler_helpers import (
    _beijing_now_naive,
    _primary_strategy_from_position,
)
from app.services.paper.smart_exit_context import build_exit_context
from app.services.paper.smart_t import build_smart_t_add_orders
from app.services.paper.smart_t_exit import build_smart_t_exit_orders
from app.services.paper.trailing_stop_state import update_position_trailing_high
from app.services.quant.runtime_parameters import get_paper_dynamic_exit

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
    intraday_bars = latest_intraday_bars([row.symbol for row in positions])
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
        context = build_exit_context(quote, intraday_bars.get(row.symbol))
        context = _attach_trailing_stop_context(
            db=db,
            account=account,
            row=row,
            price=price,
            quote_high=float(getattr(quote, "high_price", 0.0) or 0.0),
            context=context,
        )
        decision = evaluate_paper_exit(row, price=price, now=now, context=context)
        exit_model = _exit_model_shadow_payload(
            db=db,
            account=account,
            row=row,
            decision=decision,
            price=price,
            now=now,
            quote=quote,
            context=context,
            intraday_bars=intraday_bars.get(row.symbol),
        )
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
                    "action_text": decision.action_text,
                    "why": decision.why,
                    "invalid_condition": decision.invalid_condition,
                    "failure_action": decision.failure_action,
                    "fee_drag_pct": decision.fee_drag_pct,
                    "net_profit_pct": decision.net_profit_pct,
                    "vwap": context.vwap,
                    "above_vwap": context.above_vwap,
                    "volume_release_ratio": context.volume_release_ratio,
                    "high_pullback_ratio": context.high_pullback_ratio,
                    "trailing_high_price": context.trailing_high_price,
                    "trailing_stop_price": context.trailing_stop_price,
                    "dynamic_exit": True,
                    "exit_model_shadow": exit_model,
                },
            }
        )
    reason = EXIT_QUOTES_UNAVAILABLE_REASON if skipped_symbols and not orders else ""
    return orders, reason


def _exit_model_shadow_payload(
    *,
    db: Session,
    account: PaperAccount,
    row,
    decision,
    price: float,
    now,
    quote,
    context,
    intraday_bars,
) -> dict[str, Any]:
    features = build_exit_model_features(
        position=row,
        decision=decision,
        price=price,
        now=now,
        quote=quote,
        context=context,
        intraday_bars=intraday_bars or [],
        account_total_assets=float(getattr(account, "total_assets", 0.0) or 0.0),
    )
    suggestion = ExitModelAdvisor().suggest(features)
    payload = suggestion.to_dict()
    record_exit_model_shadow(
        db,
        ExitModelShadowRecord(
            account_id=int(getattr(account, "id", 0) or 0),
            position_id=int(getattr(row, "id", 0) or 0),
            symbol=str(getattr(row, "symbol", "") or ""),
            name=str(getattr(row, "name", "") or ""),
            strategy_key=features.strategy_key,
            as_of=features.as_of,
            rule_action=features.rule_action,
            rule_reason=str(decision.why or decision.reason or ""),
            rule_sell_ratio=features.rule_sell_ratio,
            model_action=suggestion.action,
            model_confidence=suggestion.confidence,
            model_reason=list(suggestion.reasons),
            model_version=suggestion.model_version,
            fallback_reason=suggestion.fallback_reason,
            feature_snapshot=features.to_dict(),
        ),
    )
    return payload


def build_smart_t_order_plan(
    *,
    db: Session,
    account: PaperAccount,
    today_orders: list[dict[str, Any]],
    used_order_count: int,
    max_orders: int,
    market_state: str = "",
) -> list[dict[str, Any]]:
    positions = PaperPositionService(db).get_positions(account.id)
    if not positions:
        return []
    prices = latest_prices([row.symbol for row in positions])
    if not prices:
        return []
    bars = latest_intraday_bars([row.symbol for row in positions])
    contexts = {row.symbol: build_exit_context(prices.get(row.symbol), bars.get(row.symbol)) for row in positions}
    params = get_paper_dynamic_exit()
    now = _beijing_now_naive()
    exit_orders = build_smart_t_exit_orders(
        db=db,
        account=account,
        positions=positions,
        prices=prices,
        contexts=contexts,
        params=params,
        now=now,
        used_order_count=used_order_count,
        max_orders=max_orders,
        market_state=market_state,
    )
    add_orders = build_smart_t_add_orders(
        account=account,
        positions=positions,
        prices=prices,
        contexts=contexts,
        today_orders=today_orders,
        params=params,
        now=now,
        used_order_count=used_order_count + len(exit_orders),
        max_orders=max_orders,
        market_state=market_state,
    )
    return [*exit_orders, *add_orders]


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
            open_price=float(getattr(quote, "open_price", 0) or 0),
            high_price=float(getattr(quote, "high_price", 0) or 0),
            low_price=float(getattr(quote, "low_price", 0) or 0),
            prev_close=float(getattr(quote, "prev_close", 0) or 0),
            change_pct=float(getattr(quote, "change_pct", 0) or 0),
            volume_ratio=float(getattr(quote, "volume_ratio", 0) or 0),
        )
    return result


def latest_intraday_bars(symbols: list[str]) -> dict[str, list[Any]]:
    try:
        return MarketDataService().get_intraday_bars_batch(
            symbols,
            period="1m",
            limit=80,
            max_workers=4,
            allow_slow_fallback=False,
        )
    except Exception:
        logger.warning("自动退出计划分时数据获取失败，本轮按静态动态止盈止损处理", exc_info=True)
        return {}


def _attach_trailing_stop_context(*, db: Session, account: PaperAccount, row, price: float, quote_high: float, context):
    params = get_paper_dynamic_exit()
    trailing_stop_pct = float(params.get("trailing_stop_pct", 2.0) or 2.0)
    high_price = update_position_trailing_high(
        db,
        account_id=int(account.id),
        position=row,
        current_price=max(price, quote_high),
    )
    stop_price = high_price * (1 - trailing_stop_pct / 100.0) if high_price > 0 else 0.0
    return replace(
        context,
        trailing_high_price=round(high_price, 4),
        trailing_stop_price=round(stop_price, 4),
    )
