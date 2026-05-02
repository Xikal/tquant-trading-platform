from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.admin_auth import require_admin_auth
from app.core.database import get_db
from app.core.paper_auth import require_paper_trading
from app.models.entities import PaperTrade, User
from app.models.schemas import (
    PaperAccountCreate,
    PaperAccountOut,
    PaperGroupedPerformanceOut,
    PaperOrderCreate,
    PaperOrderOut,
    PaperPerformanceOut,
    PaperPositionOut,
    PaperPositionsResponse,
    PaperRiskStatusOut,
    RiskEventOut,
    PaperTradeOut,
    PaperTradesResponse,
)
from app.services.intraday_confirmation_service import IntradayConfirmationService
from app.services.market_data import DataSourceError, MarketDataService
from app.services.paper import PaperAccountService, PaperOrderService, PaperPerformanceService, PaperPositionService
from app.services.paper.risk_circuit import PaperRiskCircuitBreaker
from app.services.paper.risk_control import PaperRiskControlService

router = APIRouter(prefix="/paper")
market_data = MarketDataService()


@router.get("/account", response_model=PaperAccountOut)
def get_paper_account(
    current_user: User = Depends(require_paper_trading),
    db: Session = Depends(get_db),
) -> PaperAccountOut:
    account = PaperAccountService(db).get_or_create_default(current_user.id)
    PaperAccountService(db).update_market_value(account.id)
    return _account_out(account)


@router.post("/account", response_model=PaperAccountOut)
def create_paper_account(
    payload: PaperAccountCreate,
    current_user: User = Depends(require_paper_trading),
    db: Session = Depends(get_db),
) -> PaperAccountOut:
    account = PaperAccountService(db).create_account(payload.name, Decimal(str(payload.initial_cash)), user_id=current_user.id)
    return _account_out(account)


@router.post("/account/reset", response_model=PaperAccountOut)
def reset_paper_account(
    current_user: User = Depends(require_paper_trading),
    __: None = Depends(require_admin_auth),
    db: Session = Depends(get_db),
) -> PaperAccountOut:
    service = PaperAccountService(db)
    account = service.get_or_create_default(current_user.id)
    return _account_out(service.reset_account(account.id))


@router.post("/account/pause", response_model=PaperAccountOut)
def pause_paper_account(current_user: User = Depends(require_paper_trading), db: Session = Depends(get_db)) -> PaperAccountOut:
    service = PaperAccountService(db)
    account = service.get_or_create_default(current_user.id)
    return _account_out(service.pause(account.id))


@router.post("/account/resume", response_model=PaperAccountOut)
def resume_paper_account(current_user: User = Depends(require_paper_trading), db: Session = Depends(get_db)) -> PaperAccountOut:
    service = PaperAccountService(db)
    account = service.get_or_create_default(current_user.id)
    return _account_out(service.resume(account.id))


@router.get("/positions", response_model=PaperPositionsResponse)
def list_paper_positions(
    current_user: User = Depends(require_paper_trading),
    db: Session = Depends(get_db),
) -> PaperPositionsResponse:
    account = PaperAccountService(db).get_or_create_default(current_user.id)
    rows = PaperPositionService(db).get_positions(account.id)
    items = [_position_out(row) for row in rows]
    return PaperPositionsResponse(
        positions=items,
        total_market_value=round(sum(item.market_value for item in items), 2),
        total_unrealized_pnl=round(sum(item.unrealized_pnl for item in items), 2),
    )


@router.get("/positions/{symbol}", response_model=PaperPositionOut)
def get_paper_position(
    symbol: str,
    current_user: User = Depends(require_paper_trading),
    db: Session = Depends(get_db),
) -> PaperPositionOut:
    account = PaperAccountService(db).get_or_create_default(current_user.id)
    row = PaperPositionService(db).get_position(account.id, symbol)
    if row is None:
        raise HTTPException(status_code=404, detail="模拟持仓不存在")
    return _position_out(row)


@router.post("/positions/refresh", response_model=PaperPositionsResponse)
def refresh_paper_positions(current_user: User = Depends(require_paper_trading), db: Session = Depends(get_db)) -> PaperPositionsResponse:
    account = PaperAccountService(db).get_or_create_default(current_user.id)
    position_service = PaperPositionService(db)
    positions = position_service.get_positions(account.id)
    prices: dict[str, Decimal] = {}
    symbols = [row.symbol for row in positions]
    if symbols:
        try:
            quotes = market_data.get_quotes_batch(symbols)
            prices = {symbol: Decimal(str(quote.last_price)) for symbol, quote in quotes.items()}
        except Exception:
            for row in positions:
                try:
                    quote = market_data.get_quote(row.symbol)
                    prices[row.symbol] = Decimal(str(quote.last_price))
                except Exception:
                    continue
    position_service.refresh_quotes(account.id, prices)
    db.commit()
    return _positions_response(position_service.get_positions(account.id))


@router.get("/risk", response_model=PaperRiskStatusOut)
def get_paper_risk_status(
    current_user: User = Depends(require_paper_trading),
    db: Session = Depends(get_db),
) -> PaperRiskStatusOut:
    account = PaperAccountService(db).get_or_create_default(current_user.id)
    return PaperRiskStatusOut(**PaperRiskControlService(db).account_status(account.id))


@router.post("/risk/evaluate", response_model=list[RiskEventOut])
def evaluate_paper_risk_events(
    current_user: User = Depends(require_paper_trading),
    db: Session = Depends(get_db),
) -> list[RiskEventOut]:
    account = PaperAccountService(db).get_or_create_default(current_user.id)
    return PaperRiskCircuitBreaker(db).evaluate_account(account.id)


@router.get("/risk/events", response_model=list[RiskEventOut])
def list_paper_risk_events(
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(require_paper_trading),
    db: Session = Depends(get_db),
) -> list[RiskEventOut]:
    account = PaperAccountService(db).get_or_create_default(current_user.id)
    return PaperRiskCircuitBreaker(db).list_open_events(account.id, limit=limit)


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
    return [_order_out(row) for row in rows]


@router.post("/orders", response_model=PaperOrderOut)
def create_paper_order(
    payload: PaperOrderCreate,
    current_user: User = Depends(require_paper_trading),
    db: Session = Depends(get_db),
) -> PaperOrderOut:
    account = PaperAccountService(db).get_or_create_default(current_user.id)
    quote_price, quote_time, quote_name = _resolve_quote(payload)
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
    return _order_out(order)


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
        return _order_out(order)
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
        return _order_out(service.cancel_order(order_id))
    except (LookupError, ValueError) as exc:
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
    return PaperTradesResponse(trades=[_trade_out(row) for row in rows])


@router.get("/performance", response_model=PaperPerformanceOut)
def paper_performance(
    current_user: User = Depends(require_paper_trading),
    db: Session = Depends(get_db),
) -> PaperPerformanceOut:
    account = PaperAccountService(db).get_or_create_default(current_user.id)
    return PaperPerformanceOut(**PaperPerformanceService(db).compute_overall(account.id))


@router.get("/performance/by-strategy", response_model=list[PaperGroupedPerformanceOut])
def paper_performance_by_strategy(
    current_user: User = Depends(require_paper_trading),
    db: Session = Depends(get_db),
) -> list[PaperGroupedPerformanceOut]:
    account = PaperAccountService(db).get_or_create_default(current_user.id)
    return [PaperGroupedPerformanceOut(**item) for item in PaperPerformanceService(db).compute_by_strategy(account.id)]


@router.get("/performance/by-market-state", response_model=list[PaperGroupedPerformanceOut])
def paper_performance_by_market_state(
    current_user: User = Depends(require_paper_trading),
    db: Session = Depends(get_db),
) -> list[PaperGroupedPerformanceOut]:
    account = PaperAccountService(db).get_or_create_default(current_user.id)
    return [PaperGroupedPerformanceOut(**item) for item in PaperPerformanceService(db).compute_by_market_state(account.id)]


def _resolve_quote(payload: PaperOrderCreate) -> tuple[Decimal, datetime, str]:
    if payload.current_price:
        return Decimal(str(payload.current_price)), payload.quote_time or datetime.now(), payload.name
    try:
        quote = market_data.get_quote(payload.symbol)
    except DataSourceError as exc:
        raise HTTPException(status_code=400, detail=f"无法获取模拟撮合行情: {exc}") from exc
    return Decimal(str(quote.last_price)), _parse_quote_time(quote.timestamp), quote.name


def _parse_quote_time(value: str) -> datetime:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return datetime.now()


def _account_out(row) -> PaperAccountOut:
    initial = float(row.initial_cash or 0)
    total = float(row.total_assets or 0)
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
        max_drawdown_pct=float(row.max_drawdown_pct or 0),
        status=row.status,
        today_return_pct=round((total - initial) / initial * 100, 3) if initial else 0.0,
    )


def _positions_response(rows) -> PaperPositionsResponse:
    items = [_position_out(row) for row in rows]
    return PaperPositionsResponse(
        positions=items,
        total_market_value=round(sum(item.market_value for item in items), 2),
        total_unrealized_pnl=round(sum(item.unrealized_pnl for item in items), 2),
    )


def _position_out(row) -> PaperPositionOut:
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


def _order_out(row) -> PaperOrderOut:
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


def _trade_out(row) -> PaperTradeOut:
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
        trade_time=row.trade_time,
    )


def _json_list(raw: str) -> list[str]:
    try:
        values = json.loads(raw or "[]")
        return [str(item) for item in values if item]
    except Exception:
        return []
