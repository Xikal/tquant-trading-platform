from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.routes.paper_serializers import account_out, position_out, positions_response
from app.api.routes.paper_shared import market_data
from app.core.admin_auth import require_admin_auth
from app.core.config import get_settings
from app.core.database import get_db
from app.core.paper_auth import require_paper_trading
from app.models.entities import User
from app.models.schemas import (
    PaperAccountCreate,
    PaperAccountOut,
    PaperPositionOut,
    PaperPositionsResponse,
    PaperRiskStatusOut,
    RiskEventOut,
)
from app.services.paper import PaperAccountService, PaperPositionService
from app.services.paper.risk_circuit import PaperRiskCircuitBreaker
from app.services.paper.risk_control import PaperRiskControlService

router = APIRouter()


@router.get("/account", response_model=PaperAccountOut)
def get_paper_account(
    current_user: User = Depends(require_paper_trading),
    db: Session = Depends(get_db),
) -> PaperAccountOut:
    service = PaperAccountService(db)
    account = service.get_or_create_default(current_user.id)
    if get_settings().paper_auto_trading_enabled:
        account = service.resume_if_safe_for_auto_trading(account.id)
    service.update_market_value(account.id)
    db.commit()
    db.refresh(account)
    return account_out(account)


@router.post("/account", response_model=PaperAccountOut)
def create_paper_account(
    payload: PaperAccountCreate,
    current_user: User = Depends(require_paper_trading),
    db: Session = Depends(get_db),
) -> PaperAccountOut:
    account = PaperAccountService(db).create_account(payload.name, Decimal(str(payload.initial_cash)), user_id=current_user.id)
    return account_out(account)


@router.post("/account/reset", response_model=PaperAccountOut)
def reset_paper_account(
    current_user: User = Depends(require_paper_trading),
    __: None = Depends(require_admin_auth),
    db: Session = Depends(get_db),
) -> PaperAccountOut:
    service = PaperAccountService(db)
    account = service.get_or_create_default(current_user.id)
    return account_out(service.reset_account(account.id))


@router.post("/account/pause", response_model=PaperAccountOut)
def pause_paper_account(current_user: User = Depends(require_paper_trading), db: Session = Depends(get_db)) -> PaperAccountOut:
    service = PaperAccountService(db)
    account = service.get_or_create_default(current_user.id)
    return account_out(service.pause(account.id))


@router.post("/account/resume", response_model=PaperAccountOut)
def resume_paper_account(current_user: User = Depends(require_paper_trading), db: Session = Depends(get_db)) -> PaperAccountOut:
    service = PaperAccountService(db)
    account = service.get_or_create_default(current_user.id)
    PaperRiskCircuitBreaker(db).resolve_open_events(account.id, reason="manual_review_resume")
    return account_out(service.resume(account.id))


@router.get("/positions", response_model=PaperPositionsResponse)
def list_paper_positions(
    current_user: User = Depends(require_paper_trading),
    db: Session = Depends(get_db),
) -> PaperPositionsResponse:
    account = PaperAccountService(db).get_or_create_default(current_user.id)
    rows = PaperPositionService(db).get_positions(account.id)
    items = [position_out(row) for row in rows]
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
    return position_out(row)


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
    PaperAccountService(db).update_market_value(account.id)
    db.commit()
    return positions_response(position_service.get_positions(account.id))


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
