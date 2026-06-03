from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.paper_auth import require_paper_trading
from app.models.entities import User
from app.services.trading_experience.schemas import (
    BoardFilter,
    HoldingDisciplineResponse,
    LimitUpFollowthroughResponse,
    RelativeStrengthResponse,
    ReviewPoolResponse,
    TTradeAttributionResponse,
    TradeJournalEntryCreate,
    TradeJournalEntryOut,
    TradeJournalResponse,
    TradingExperienceReadinessResponse,
    VolumePositionTagResponse,
)
from app.services.trading_experience.service import TradingExperienceService

router = APIRouter(prefix="/trading-experience", dependencies=[Depends(get_current_user)])


@router.get("/readiness", response_model=TradingExperienceReadinessResponse)
def readiness(db: Session = Depends(get_db)) -> TradingExperienceReadinessResponse:
    return TradingExperienceService(db).readiness()


@router.get("/review-pool", response_model=ReviewPoolResponse)
def get_review_pool(
    pool_date: date | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    board_filter: BoardFilter = "include_all",
    db: Session = Depends(get_db),
) -> ReviewPoolResponse:
    return TradingExperienceService(db).review_pool(pool_date=pool_date, limit=limit, board_filter=board_filter)


@router.get("/trade-journal", response_model=TradeJournalResponse)
def get_trade_journal(
    account_id: int | None = None,
    symbol: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_paper_trading),
) -> TradeJournalResponse:
    return TradingExperienceService(db).trade_journal(
        user_id=getattr(current_user, "id", None),
        account_id=account_id,
        symbol=symbol,
        limit=limit,
    )


@router.post("/trade-journal", response_model=TradeJournalEntryOut)
def create_trade_journal(
    payload: TradeJournalEntryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_paper_trading),
) -> TradeJournalEntryOut:
    try:
        return TradingExperienceService(db).create_trade_journal(payload, user_id=getattr(current_user, "id", None))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/volume-position-tags/{symbol}", response_model=VolumePositionTagResponse)
def get_volume_position_tags(
    symbol: str,
    trade_date: date | None = None,
    db: Session = Depends(get_db),
) -> VolumePositionTagResponse:
    return TradingExperienceService(db).volume_position_tags(symbol, trade_date=trade_date)


@router.get("/relative-strength", response_model=RelativeStrengthResponse)
def get_relative_strength(
    trade_date: date | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    db: Session = Depends(get_db),
) -> RelativeStrengthResponse:
    return TradingExperienceService(db).relative_strength(trade_date=trade_date, limit=limit)


@router.get("/holding-discipline", response_model=HoldingDisciplineResponse)
def get_holding_discipline(
    account_id: int | None = None,
    current_user: User = Depends(require_paper_trading),
    db: Session = Depends(get_db),
) -> HoldingDisciplineResponse:
    return TradingExperienceService(db).holding_discipline(account_id=account_id, user_id=current_user.id)


@router.get("/limit-up-followthrough", response_model=LimitUpFollowthroughResponse)
def get_limit_up_followthrough(
    trade_date: date | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    db: Session = Depends(get_db),
) -> LimitUpFollowthroughResponse:
    return TradingExperienceService(db).limit_up_followthrough(trade_date=trade_date, limit=limit)


@router.get("/t-trade-attribution", response_model=TTradeAttributionResponse)
def get_t_trade_attribution(
    account_id: int | None = None,
    days: Annotated[int, Query(ge=1, le=120)] = 30,
    current_user: User = Depends(require_paper_trading),
    db: Session = Depends(get_db),
) -> TTradeAttributionResponse:
    return TradingExperienceService(db).t_trade_attribution(account_id=account_id, days=days, user_id=current_user.id)
