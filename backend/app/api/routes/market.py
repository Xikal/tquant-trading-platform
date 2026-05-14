from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.auth import get_current_user
from app.core.timezone import beijing_now_string
from app.core.role_permissions import require_research_access
from app.models.schema_defs.market import (
    IntradayAnomalyResponse,
    MarketBreadthResponse,
    MarketTradingSessionResponse,
    MarketModelValidationResponse,
    PairedHedgeResearchResponse,
    SectorEtfT0Response,
)
from app.models.entities import User
from app.services.intraday_anomaly import IntradayAnomalyService
from app.services.market_data import MarketDataService
from app.services.market.regime_quality import market_regime_quality_text
from app.services.market.trading_session import current_a_share_trading_session
from app.services.paired_hedge_research import PairedHedgeResearchService
from app.services.sector_etf_t0 import SectorEtfT0Service
from app.services.user_sector_preferences import UserSectorPreferenceService, filter_monitor_snapshot_payload
from app.core.database import get_db
from sqlalchemy.orm import Session

router = APIRouter(prefix="/market", dependencies=[Depends(get_current_user)])
market_data = MarketDataService()
sector_etf_t0_service = SectorEtfT0Service(market_data=market_data)
intraday_anomaly_service = IntradayAnomalyService(market_data=market_data)
paired_hedge_research_service = PairedHedgeResearchService(market_data=market_data)


@router.get("/breadth", response_model=MarketBreadthResponse)
def market_breadth() -> MarketBreadthResponse:
    """Return compact market breadth and sentiment data for the monitor page."""

    regime = market_data.get_market_regime_fast()
    return MarketBreadthResponse(
        updated_at=beijing_now_string(),
        state=regime.state,
        state_text=regime.label,
        breadth_ready=regime.breadth_ready,
        emotion_ready=regime.emotion_ready,
        stock_up_ratio=round(regime.stock_up_ratio, 4),
        stock_median_change=round(regime.stock_median_change, 4),
        largecap_change=round(regime.largecap_change, 4),
        smallcap_change=round(regime.smallcap_change, 4),
        style_divergence=round(regime.style_divergence, 4),
        limit_up_count=int(regime.limit_up_count or 0),
        limit_down_count=regime.limit_down_count,
        broken_board_ratio=round(regime.broken_board_ratio, 4),
        promotion_ratio=round(regime.promotion_ratio, 4),
        board_height=int(regime.board_height or 0),
        hot_industries=regime.hot_industries[:8],
        hot_turnover=round(regime.hot_turnover, 4),
        hot_overlap_ratio=round(regime.hot_overlap_ratio, 4),
        data_quality_text=market_regime_quality_text(regime),
    )


@router.get("/trading-session", response_model=MarketTradingSessionResponse)
def market_trading_session() -> MarketTradingSessionResponse:
    """Return backend-authoritative A-share trading session status."""

    status = current_a_share_trading_session()
    return MarketTradingSessionResponse(
        updated_at=beijing_now_string(),
        is_trading_day=status.is_trading_day,
        is_trading_now=status.is_trading_now,
        current_time=status.current_time,
        timezone=status.timezone,
        data_quality_text=status.data_quality_text,
    )


@router.get("/sector-etf-t0", response_model=SectorEtfT0Response)
def sector_etf_t0(
    limit: int = 8,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SectorEtfT0Response:
    response = sector_etf_t0_service.build(db, limit=max(1, min(limit, 20)))
    excluded = UserSectorPreferenceService(db).get_excluded_sector_set(current_user.id)
    if not excluded:
        return response
    payload = filter_monitor_snapshot_payload({"sector_etf_t0": response.model_dump()}, excluded)
    return SectorEtfT0Response.model_validate(payload["sector_etf_t0"])


@router.get("/sector-etf-t0/validation", response_model=MarketModelValidationResponse)
def sector_etf_t0_validation(
    limit: int = 8,
    db: Session = Depends(get_db),
) -> MarketModelValidationResponse:
    response = sector_etf_t0_service.validation_report(db, limit=max(1, min(limit, 20)))
    db.commit()
    return response


@router.get("/paired-hedge-research", response_model=PairedHedgeResearchResponse)
def paired_hedge_research(
    limit: int = 8,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PairedHedgeResearchResponse:
    require_research_access(current_user)
    return paired_hedge_research_service.build(db, limit=max(1, min(limit, 20)))


@router.get("/intraday-anomaly/{symbol}", response_model=IntradayAnomalyResponse)
def intraday_anomaly(symbol: str, db: Session = Depends(get_db)) -> IntradayAnomalyResponse:
    response = intraday_anomaly_service.detect(symbol.strip())
    intraday_anomaly_service.record_observation(db, response)
    db.commit()
    return response


@router.get("/intraday-anomaly-validation", response_model=MarketModelValidationResponse)
def intraday_anomaly_validation(
    symbols: str = "510300,300059,000001,600000,002594",
    db: Session = Depends(get_db),
) -> MarketModelValidationResponse:
    symbol_list = [item.strip() for item in symbols.split(",") if item.strip()]
    response = intraday_anomaly_service.validation_report(symbol_list, db=db)
    db.commit()
    return response
