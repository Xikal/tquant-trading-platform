from __future__ import annotations

from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes.paper_serializers import order_out, trade_out, trade_tag_out
from app.api.routes.paper_shared import ensure_trade_belongs_to_account, resolve_quote
from app.core.database import get_db
from app.core.paper_auth import require_paper_trading
from app.models.entities import PaperTrade, PaperTradeTag, User
from app.models.schemas import (
    PaperOrderCreate,
    PaperOrderOut,
    PaperTradeTagCreate,
    PaperTradeTagOut,
    PaperTradesResponse,
)
from app.services.intraday_confirmation_service import IntradayConfirmationService
from app.services.paper import PaperAccountService, PaperOrderService
from app.services.paper.risk_circuit import PaperRiskCircuitBreaker

router = APIRouter()


@router.get("/orders", response_model=list[PaperOrderOut])
def list_paper_orders(
    symbol: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(require_paper_trading),
    db: Session = Depends(get_db),
) -> list[PaperOrderOut]:
    account = PaperAccountService(db).get_or_create_default(current_user.id)
    rows = PaperOrderService(db).get_orders(account_id=account.id, symbol=symbol, status=status, limit=limit)
    return [order_out(row) for row in rows]


@router.post("/orders", response_model=PaperOrderOut)
def create_paper_order(
    payload: PaperOrderCreate,
    current_user: User = Depends(require_paper_trading),
    db: Session = Depends(get_db),
) -> PaperOrderOut:
    account = PaperAccountService(db).get_or_create_default(current_user.id)
    quote_price, quote_time, quote_name = resolve_quote(payload)
    intraday_confirmed = True
    if payload.require_intraday_confirmation and payload.side == "buy":
        confirmations = IntradayConfirmationService(db).confirm_symbols(
            [payload.symbol.strip()],
            period="1m",
            limit=120,
        )
        intraday_confirmed = bool(
            confirmations and (confirmations[0].confirmed or confirmations[0].late_confirmed)
        )
    try:
        order = PaperOrderService(db).create_order(
            account_id=account.id,
            symbol=payload.symbol.strip(),
            name=payload.name or quote_name or payload.symbol,
            side=payload.side,
            order_type=payload.order_type,
            quantity=payload.quantity,
            price=Decimal(str(payload.price)) if payload.price else None,
            source=payload.source,
            strategy_key=payload.strategy_key,
            reason=payload.reason,
            signal_snapshot=payload.signal_snapshot,
            current_price=quote_price,
            quote_time=quote_time,
            is_suspended=payload.is_suspended,
            up_limit=Decimal(str(payload.up_limit)) if payload.up_limit else None,
            down_limit=Decimal(str(payload.down_limit)) if payload.down_limit else None,
            intraday_confirmed=intraday_confirmed,
        )
        PaperRiskCircuitBreaker(db).evaluate_account(account.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return order_out(order)


@router.get("/orders/{order_id}", response_model=PaperOrderOut)
def get_paper_order(
    order_id: int,
    current_user: User = Depends(require_paper_trading),
    db: Session = Depends(get_db),
) -> PaperOrderOut:
    try:
        order = PaperOrderService(db).get_order(order_id)
        account = PaperAccountService(db).get_or_create_default(current_user.id)
        if order.account_id != account.id:
            raise LookupError("模拟委托不存在")
        return order_out(order)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/orders/{order_id}/cancel", response_model=PaperOrderOut)
def cancel_paper_order(
    order_id: int,
    current_user: User = Depends(require_paper_trading),
    db: Session = Depends(get_db),
) -> PaperOrderOut:
    try:
        service = PaperOrderService(db)
        order = service.get_order(order_id)
        account = PaperAccountService(db).get_or_create_default(current_user.id)
        if order.account_id != account.id:
            raise LookupError("模拟委托不存在")
        return order_out(service.cancel_order(order_id))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/trades", response_model=PaperTradesResponse)
def list_paper_trades(
    symbol: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=300),
    current_user: User = Depends(require_paper_trading),
    db: Session = Depends(get_db),
) -> PaperTradesResponse:
    account = PaperAccountService(db).get_or_create_default(current_user.id)
    statement = select(PaperTrade).where(PaperTrade.account_id == account.id)
    if symbol:
        statement = statement.where(PaperTrade.symbol == symbol)
    rows = db.execute(statement.order_by(PaperTrade.trade_time.desc()).limit(limit)).scalars().all()
    return PaperTradesResponse(trades=[trade_out(row) for row in rows])


@router.get("/trades/{trade_id}/tags", response_model=list[PaperTradeTagOut])
def list_paper_trade_tags(
    trade_id: int,
    current_user: User = Depends(require_paper_trading),
    db: Session = Depends(get_db),
) -> list[PaperTradeTagOut]:
    account = PaperAccountService(db).get_or_create_default(current_user.id)
    ensure_trade_belongs_to_account(db, trade_id, account.id)
    rows = (
        db.execute(
            select(PaperTradeTag)
            .where(PaperTradeTag.trade_id == trade_id, PaperTradeTag.account_id == account.id)
            .order_by(PaperTradeTag.created_at.desc())
        )
        .scalars()
        .all()
    )
    return [trade_tag_out(row) for row in rows]


@router.post("/trades/{trade_id}/tags", response_model=PaperTradeTagOut)
def add_paper_trade_tag(
    trade_id: int,
    payload: PaperTradeTagCreate,
    current_user: User = Depends(require_paper_trading),
    db: Session = Depends(get_db),
) -> PaperTradeTagOut:
    account = PaperAccountService(db).get_or_create_default(current_user.id)
    ensure_trade_belongs_to_account(db, trade_id, account.id)
    tag = payload.tag.strip()
    row = (
        db.execute(
            select(PaperTradeTag).where(
                PaperTradeTag.trade_id == trade_id,
                PaperTradeTag.account_id == account.id,
                PaperTradeTag.tag == tag,
            )
        )
        .scalars()
        .first()
    )
    if row is None:
        row = PaperTradeTag(
            trade_id=trade_id,
            account_id=account.id,
            user_id=current_user.id,
            tag=tag,
            note=payload.note.strip(),
        )
        db.add(row)
    else:
        row.note = payload.note.strip()
    db.commit()
    db.refresh(row)
    return trade_tag_out(row)


@router.delete("/trades/{trade_id}/tags/{tag_id}")
def delete_paper_trade_tag(
    trade_id: int,
    tag_id: int,
    current_user: User = Depends(require_paper_trading),
    db: Session = Depends(get_db),
) -> dict:
    account = PaperAccountService(db).get_or_create_default(current_user.id)
    ensure_trade_belongs_to_account(db, trade_id, account.id)
    row = db.get(PaperTradeTag, tag_id)
    if row is None or row.trade_id != trade_id or row.account_id != account.id:
        raise HTTPException(status_code=404, detail="交易标签不存在")
    db.delete(row)
    db.commit()
    return {"message": "标签已删除", "tag_id": tag_id}
