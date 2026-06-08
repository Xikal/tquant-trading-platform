from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.timezone import beijing_today
from app.models.entities import PaperPerformanceSnapshot
from app.models.schemas import (
    PaperAccountOut,
    PaperOrderOut,
    PaperPositionOut,
    PaperPositionsResponse,
    PaperTradeOut,
    PaperTradeTagOut,
)
from app.services.paper.dynamic_exit import evaluate_paper_exit
from app.services.paper.exit_model_advisor import ExitModelAdvisor
from app.services.paper.exit_model_features import build_exit_model_features
from app.services.paper.fees import commission_warning_text
from app.services.paper.main_force_paper_advisor import build_main_force_paper_advice, latest_main_force_advice_for_symbol
from app.services.paper.money import CENT, to_decimal
from app.services.paper.reasons import normalize_entry_reason, normalize_exit_reason


class PaperPositionQuoteOverlay:
    def __init__(
        self,
        *,
        price: Decimal,
        market_value: Decimal,
        unrealized_pnl: Decimal,
        unrealized_pnl_pct: Decimal,
        timestamp: str = "",
        quality: str = "snapshot",
        quality_text: str = "持仓快照价",
        source: str = "paper_position_snapshot",
        is_stale: bool = True,
        day_change_pct: float | None = None,
        prev_close: float | None = None,
    ) -> None:
        self.price = price
        self.market_value = market_value
        self.unrealized_pnl = unrealized_pnl
        self.unrealized_pnl_pct = unrealized_pnl_pct
        self.timestamp = timestamp
        self.quality = quality
        self.quality_text = quality_text
        self.source = source
        self.is_stale = is_stale
        self.day_change_pct = day_change_pct
        self.prev_close = prev_close


def paper_position_live_overlays(rows, *, market_data) -> dict[str, PaperPositionQuoteOverlay]:  # noqa: ANN001
    symbols = [str(getattr(row, "symbol", "") or "") for row in rows if getattr(row, "symbol", "")]
    if not symbols:
        return {}
    try:
        quotes = market_data.get_quotes_batch(
            list(dict.fromkeys(symbols)),
            force_refresh=False,
            allow_slow_fallback=False,
        )
    except Exception:
        quotes = {}
    if not isinstance(quotes, dict):
        quotes = {}

    overlays: dict[str, PaperPositionQuoteOverlay] = {}
    for row in rows:
        symbol = str(getattr(row, "symbol", "") or "")
        quote = quotes.get(symbol)
        price = _quote_price(quote)
        if price is None or price <= 0:
            overlays[symbol] = _snapshot_overlay(row)
            continue
        overlays[symbol] = _overlay_from_quote(row, quote, price=price)
    return overlays


def account_out(row, *, db: Session | None = None) -> PaperAccountOut:
    initial = float(row.initial_cash or 0)
    total = float(row.total_assets or 0)
    total_return_pct = round((total - initial) / initial * 100, 3) if initial else 0.0
    return PaperAccountOut(
        id=row.id,
        user_id=row.user_id,
        name=row.name,
        initial_cash=initial,
        cash_available=float(row.cash_available or 0),
        frozen_cash=float(row.frozen_cash or 0),
        market_value=float(row.market_value or 0),
        total_assets=total,
        realized_pnl=float(row.realized_pnl or 0),
        unrealized_pnl=float(row.unrealized_pnl or 0),
        total_return_pct=total_return_pct,
        today_pnl=_paper_account_today_pnl(db, account_id=int(row.id), total_assets=total),
        max_drawdown_pct=float(row.max_drawdown_pct or 0),
        status=row.status,
        today_return_pct=total_return_pct,
    )


def _paper_account_today_pnl(db: Session | None, *, account_id: int, total_assets: float) -> float | None:
    if db is None:
        return None
    snapshot = (
        db.execute(
            select(PaperPerformanceSnapshot)
            .where(
                PaperPerformanceSnapshot.account_id == account_id,
                PaperPerformanceSnapshot.snapshot_date < beijing_today(),
            )
            .order_by(PaperPerformanceSnapshot.snapshot_date.desc())
            .limit(1)
        )
        .scalars()
        .first()
    )
    if snapshot is None:
        return None
    return round(total_assets - float(snapshot.total_assets or 0), 2)


def account_out_with_positions_overlay(row, rows, overlays: dict[str, PaperPositionQuoteOverlay], *, db: Session | None = None) -> PaperAccountOut:  # noqa: ANN001
    output = account_out(row, db=db)
    market_value = sum((overlays.get(str(getattr(item, "symbol", "") or "")) or _snapshot_overlay(item)).market_value for item in rows)
    unrealized = sum((overlays.get(str(getattr(item, "symbol", "") or "")) or _snapshot_overlay(item)).unrealized_pnl for item in rows)
    output.market_value = round(float(market_value), 2)
    output.unrealized_pnl = round(float(unrealized), 2)
    output.total_assets = round(float(to_decimal(row.cash_available) + market_value), 2)
    initial = float(row.initial_cash or 0)
    output.total_return_pct = round((output.total_assets - initial) / initial * 100, 3) if initial else 0.0
    output.today_return_pct = output.total_return_pct
    output.today_pnl = _paper_account_today_pnl(db, account_id=int(row.id), total_assets=output.total_assets)
    return output


def positions_response(rows, *, db: Session | None = None, quote_overlays: dict[str, PaperPositionQuoteOverlay] | None = None) -> PaperPositionsResponse:
    items = [position_out(row, db=db, quote_overlay=(quote_overlays or {}).get(str(row.symbol or ""))) for row in rows]
    return PaperPositionsResponse(
        positions=items,
        total_market_value=round(sum(item.market_value for item in items), 2),
        total_unrealized_pnl=round(sum(item.unrealized_pnl for item in items), 2),
    )


def position_out(row, *, db: Session | None = None, quote_overlay: PaperPositionQuoteOverlay | None = None) -> PaperPositionOut:
    now = datetime.now()
    overlay = quote_overlay or _snapshot_overlay(row)
    decision = evaluate_paper_exit(
        row,
        price=float(overlay.price or 0),
        now=now,
    )
    exit_model = ExitModelAdvisor().suggest(
        build_exit_model_features(
            position=row,
            decision=decision,
            price=float(overlay.price or 0),
            now=now,
        )
    )
    main_force_advice = _json_dict(getattr(row, "main_force_advice_json", "") or "")
    if not main_force_advice and db is not None:
        main_force_advice = latest_main_force_advice_for_symbol(db, str(row.symbol or ""))
    return PaperPositionOut(
        id=row.id,
        symbol=row.symbol,
        name=row.name,
        quantity=row.quantity,
        available_quantity=row.available_quantity,
        frozen_quantity=row.frozen_quantity,
        cost_basis=float(row.cost_basis or 0),
        latest_price=float(overlay.price) if overlay.price is not None else None,
        quote_timestamp=overlay.timestamp,
        quote_data_quality=overlay.quality,
        quote_data_quality_text=overlay.quality_text,
        quote_source=overlay.source,
        quote_is_stale=overlay.is_stale,
        day_change_pct=overlay.day_change_pct,
        prev_close=overlay.prev_close,
        market_value=float(overlay.market_value or 0),
        unrealized_pnl=float(overlay.unrealized_pnl or 0),
        unrealized_pnl_pct=float(overlay.unrealized_pnl_pct or 0),
        strategy_sources=_json_list(row.strategy_sources),
        opened_at=row.opened_at,
        smart_exit_action=decision.code,
        smart_exit_text=decision.action_text,
        smart_exit_reason=decision.why or decision.reason,
        smart_exit_invalid_condition=decision.invalid_condition,
        smart_exit_failure_action=decision.failure_action,
        smart_exit_quantity=decision.quantity,
        smart_exit_net_profit_pct=decision.net_profit_pct,
        smart_exit_fee_drag_pct=decision.fee_drag_pct,
        exit_model_shadow=exit_model.to_dict(),
        main_force_advice=main_force_advice,
        main_force_paper_advice=build_main_force_paper_advice(
            candidate=None,
            main_force_advice=main_force_advice,
            risk_allowed=False,
            current_position_pct=0.0,
        ),
    )


def _overlay_from_quote(row, quote: Any, *, price: Decimal) -> PaperPositionQuoteOverlay:  # noqa: ANN001
    quantity = Decimal(int(getattr(row, "quantity", 0) or 0))
    cost = to_decimal(getattr(row, "cost_basis", 0) or 0)
    market_value = price * quantity
    unrealized = (price - cost) * quantity
    cost_amount = cost * Decimal(max(int(quantity), 1))
    quality = str(_quote_value(quote, "data_quality") or _quote_value(quote, "source_quality") or "fresh")
    is_stale = bool(_quote_value(quote, "is_stale")) or quality not in {"fresh", "ok"}
    return PaperPositionQuoteOverlay(
        price=price,
        market_value=market_value,
        unrealized_pnl=unrealized,
        unrealized_pnl_pct=unrealized / max(cost_amount, CENT) * 100,
        timestamp=str(_quote_value(quote, "timestamp") or ""),
        quality=quality,
        quality_text="实时行情已叠加" if not is_stale else "行情缓存已叠加",
        source=str(_quote_value(quote, "data_source") or _quote_value(quote, "source_quality") or "quote_cache"),
        is_stale=is_stale,
        day_change_pct=_float_or_none(_quote_value(quote, "change_pct")),
        prev_close=_float_or_none(_quote_value(quote, "prev_close")),
    )


def _snapshot_overlay(row) -> PaperPositionQuoteOverlay:  # noqa: ANN001
    price = to_decimal(getattr(row, "latest_price", 0) or 0)
    quantity = Decimal(int(getattr(row, "quantity", 0) or 0))
    cost = to_decimal(getattr(row, "cost_basis", 0) or 0)
    market_value = price * quantity if price > 0 else to_decimal(getattr(row, "market_value", 0) or 0)
    unrealized = (price - cost) * quantity if price > 0 else to_decimal(getattr(row, "unrealized_pnl", 0) or 0)
    cost_amount = cost * Decimal(max(int(quantity), 1))
    return PaperPositionQuoteOverlay(
        price=price,
        market_value=market_value,
        unrealized_pnl=unrealized,
        unrealized_pnl_pct=unrealized / max(cost_amount, CENT) * 100,
    )


def _quote_price(quote: Any) -> Decimal | None:
    if quote is None:
        return None
    for key in ("last_price", "latest_price", "price"):
        value = _quote_value(quote, key)
        try:
            parsed = Decimal(str(value))
        except Exception:
            continue
        if parsed > 0:
            return parsed
    return None


def _quote_value(quote: Any, key: str) -> Any:
    if isinstance(quote, dict):
        return quote.get(key)
    return getattr(quote, key, None)


def _float_or_none(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed


def order_out(row) -> PaperOrderOut:
    return PaperOrderOut(
        id=row.id,
        account_id=row.account_id,
        symbol=row.symbol,
        name=row.name,
        side=row.side,
        order_type=row.order_type,
        price=float(row.price) if row.price is not None else None,
        quantity=row.quantity,
        filled_quantity=row.filled_quantity,
        avg_fill_price=float(row.avg_fill_price) if row.avg_fill_price is not None else None,
        status=row.status,
        reject_reason=row.reject_reason,
        source=row.source,
        strategy_key=row.strategy_key,
        reason=row.reason,
        created_at=row.created_at,
    )


def trade_out(row) -> PaperTradeOut:
    entry_reason = normalize_entry_reason(row.entry_reason, source="")
    exit_reason = normalize_exit_reason(row.exit_reason, source="")
    return PaperTradeOut(
        id=row.id,
        order_id=row.order_id,
        account_id=row.account_id,
        symbol=row.symbol,
        side=row.side,
        price=float(row.price or 0),
        quantity=row.quantity,
        gross_amount=float(row.gross_amount or 0),
        commission=float(row.commission or 0),
        stamp_tax=float(row.stamp_tax or 0),
        transfer_fee=float(row.transfer_fee or 0),
        net_amount=float(row.net_amount or 0),
        strategy_key=row.strategy_key,
        entry_reason=entry_reason.text if row.side == "buy" else row.entry_reason or "",
        entry_reason_code=entry_reason.code if row.side == "buy" else "",
        exit_reason=exit_reason.text if row.side == "sell" else row.exit_reason or "",
        exit_reason_code=exit_reason.code if row.side == "sell" else "",
        commission_warning=commission_warning_text(
            gross_amount=row.gross_amount or 0,
            total_fee=(row.commission or 0) + (row.stamp_tax or 0) + (row.transfer_fee or 0),
        ),
        trade_time=row.trade_time,
    )


def trade_tag_out(row) -> PaperTradeTagOut:
    return PaperTradeTagOut(
        id=row.id,
        trade_id=row.trade_id,
        tag=row.tag,
        note=row.note,
        created_at=row.created_at,
    )


def _json_list(raw: str) -> list[str]:
    try:
        values = json.loads(raw or "[]")
        return [str(item) for item in values if item]
    except Exception:
        return []


def _json_dict(raw: str) -> dict:
    try:
        value = json.loads(raw or "{}")
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}
