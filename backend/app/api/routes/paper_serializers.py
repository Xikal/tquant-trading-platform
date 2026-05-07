from __future__ import annotations

import json

from app.models.schemas import (
    PaperAccountOut,
    PaperOrderOut,
    PaperPositionOut,
    PaperPositionsResponse,
    PaperTradeOut,
    PaperTradeTagOut,
)
from app.services.paper.fees import commission_warning_text
from app.services.paper.reasons import normalize_entry_reason, normalize_exit_reason


def account_out(row) -> PaperAccountOut:
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
        max_drawdown_pct=float(row.max_drawdown_pct or 0),
        status=row.status,
        today_return_pct=total_return_pct,
    )


def positions_response(rows) -> PaperPositionsResponse:
    items = [position_out(row) for row in rows]
    return PaperPositionsResponse(
        positions=items,
        total_market_value=round(sum(item.market_value for item in items), 2),
        total_unrealized_pnl=round(sum(item.unrealized_pnl for item in items), 2),
    )


def position_out(row) -> PaperPositionOut:
    return PaperPositionOut(
        id=row.id,
        symbol=row.symbol,
        name=row.name,
        quantity=row.quantity,
        available_quantity=row.available_quantity,
        frozen_quantity=row.frozen_quantity,
        cost_basis=float(row.cost_basis or 0),
        latest_price=float(row.latest_price) if row.latest_price is not None else None,
        market_value=float(row.market_value or 0),
        unrealized_pnl=float(row.unrealized_pnl or 0),
        unrealized_pnl_pct=float(row.unrealized_pnl_pct or 0),
        strategy_sources=_json_list(row.strategy_sources),
        opened_at=row.opened_at,
    )


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
