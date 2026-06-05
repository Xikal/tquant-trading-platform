from __future__ import annotations

import json
from datetime import datetime

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
from app.services.paper.reasons import normalize_entry_reason, normalize_exit_reason


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


def positions_response(rows, *, db: Session | None = None) -> PaperPositionsResponse:
    items = [position_out(row, db=db) for row in rows]
    return PaperPositionsResponse(
        positions=items,
        total_market_value=round(sum(item.market_value for item in items), 2),
        total_unrealized_pnl=round(sum(item.unrealized_pnl for item in items), 2),
    )


def position_out(row, *, db: Session | None = None) -> PaperPositionOut:
    now = datetime.now()
    decision = evaluate_paper_exit(
        row,
        price=float(row.latest_price or 0),
        now=now,
    )
    exit_model = ExitModelAdvisor().suggest(
        build_exit_model_features(
            position=row,
            decision=decision,
            price=float(row.latest_price or 0),
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
        latest_price=float(row.latest_price) if row.latest_price is not None else None,
        market_value=float(row.market_value or 0),
        unrealized_pnl=float(row.unrealized_pnl or 0),
        unrealized_pnl_pct=float(row.unrealized_pnl_pct or 0),
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
