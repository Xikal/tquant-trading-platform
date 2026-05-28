from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.core.admin_auth import require_admin_auth
from app.core.auth import get_current_user
from app.core.timezone import beijing_today
from app.core.timezone import beijing_now_string
from app.core.role_permissions import require_research_access
from app.models.schema_defs.market import (
    EtfMinuteSnapshotBatchResponse,
    EtfUniverseAdminResponse,
    EtfUniverseApplyRequest,
    EtfUniverseMutationResponse,
    EtfUniverseProfileOut,
    EtfUniverseRepairDraftRequest,
    EtfUniverseRollbackRequest,
    EtfUniverseResponse,
    EtfUniverseValidateRequest,
    IntradayKeyLevelResponse,
    IntradayAnomalyResponse,
    IntradayMarketPulse,
    MarketHourlySnapshotHistoryResponse,
    MarketBreadthResponse,
    MarketPulseHistoryResponse,
    MarketReviewHistoryResponse,
    MarketReviewSummaryResponse,
    MarketTradingSessionResponse,
    MarketModelValidationResponse,
    PairedHedgeResearchResponse,
    SectorRelativeStrengthResponse,
    SectorEtfT0Response,
)
from app.models.entities import User
from app.models.schema_defs.phase4 import RuntimeTaskCreate
from app.services.intraday_anomaly import IntradayAnomalyService
from app.services.intraday_key_levels import IntradayKeyLevelService
from app.services.alternative_data import AlternativeDataSentimentService
from app.services.arbitrage_research import build_multi_exchange_arbitrage_research
from app.services.market_data import MarketDataService
from app.services.market.regime_quality import market_regime_quality_text
from app.services.market.autofill import MarketDataAutofillService
from app.services.market.hourly_snapshot import latest_hourly_all_market_snapshot
from app.services.market.pulse import build_intraday_market_pulse
from app.services.market.pulse_cache import latest_pulse_or_placeholder
from app.services.market.pulse_history import (
    list_hourly_snapshot_history,
    list_market_pulse_events,
    record_market_pulse_event,
)
from app.services.market.review import build_market_review_summary, list_market_review_history
from app.services.market.trading_session import current_a_share_trading_session
from app.services.market.go_read_client import load_go_etf_minute_snapshots
from app.services.etf.universe import ETF_UNIVERSE_VERSION, EtfCategory, list_etf_profiles
from app.services.etf.universe_admin import EtfUniverseAdminService
from app.services.paired_hedge_research import PairedHedgeResearchService
from app.services.sector_etf_t0 import SectorEtfT0Service
from app.services.tasks import RuntimeTaskQueue
from app.services.user_sector_preferences import UserSectorPreferenceService, filter_monitor_snapshot_payload
from app.core.database import get_db
from sqlalchemy.orm import Session

router = APIRouter(prefix="/market", dependencies=[Depends(get_current_user)])
market_data = MarketDataService()
sector_etf_t0_service = SectorEtfT0Service(market_data=market_data)
intraday_anomaly_service = IntradayAnomalyService(market_data=market_data)
intraday_key_level_service = IntradayKeyLevelService(market_data=market_data)
paired_hedge_research_service = PairedHedgeResearchService(market_data=market_data)


@router.get("/breadth", response_model=MarketBreadthResponse)
def market_breadth(
    realtime: Annotated[bool, Query(description="是否同步刷新实时市场广度/情绪快照")] = True,
    db: Session = Depends(get_db),
) -> MarketBreadthResponse:
    """Return compact market breadth and sentiment data for the monitor page."""

    if realtime and hasattr(market_data, "get_market_regime"):
        regime = market_data.get_market_regime()
    else:
        regime = market_data.get_market_regime_fast()
    response = _market_breadth_response(regime, db)
    if hasattr(db, "commit") and hasattr(db, "flush") and hasattr(db, "execute"):
        autofill = MarketDataAutofillService(db).fill_for_pulse(
            market_breadth=response,
            sector_relative_strength=market_data.sector_relative_strength_rank(db, limit=8, per_sector_limit=8),
            trade_date=beijing_today().isoformat(),
        )
        return autofill.market_breadth or response
    return response


@router.get("/pulse", response_model=IntradayMarketPulse)
def market_pulse(
    refresh: Annotated[str, Query(pattern="^(cache|async|sync)$")] = "cache",
    db: Session = Depends(get_db),
) -> IntradayMarketPulse:
    if refresh != "sync":
        pulse, needs_refresh = latest_pulse_or_placeholder(db, trade_date=beijing_today().isoformat())
        if needs_refresh or refresh == "async":
            _enqueue_market_pulse_refresh(db, reason=f"market_pulse_{refresh}")
        return pulse
    pulse = build_market_pulse_sync(db)
    if hasattr(db, "add") and hasattr(db, "commit"):
        record_market_pulse_event(db, pulse)
        db.commit()
    return pulse


def build_market_pulse_sync(db: Session) -> IntradayMarketPulse:
    breadth = market_breadth(realtime=False, db=db)
    sector_strength = market_data.sector_relative_strength_rank(db, limit=8, per_sector_limit=8)
    autofill_service = MarketDataAutofillService(db) if hasattr(db, "commit") and hasattr(db, "flush") and hasattr(db, "execute") else None
    return build_intraday_market_pulse(
        market_breadth=breadth,
        sector_relative_strength=sector_strength,
        autofill_service=autofill_service,
        trade_date=beijing_today().isoformat(),
    )


def _enqueue_market_pulse_refresh(db: Session, *, reason: str) -> None:
    try:
        RuntimeTaskQueue(db).enqueue(
            RuntimeTaskCreate(
                task_type="market_pulse_refresh",
                payload={"trade_date": beijing_today().isoformat(), "reason": reason},
                priority=55,
                idempotency_key=f"market_pulse_refresh:{beijing_today().isoformat()}",
                max_attempts=2,
            )
        )
    except Exception:
        pass


@router.get("/pulse/history", response_model=MarketPulseHistoryResponse)
def market_pulse_history(
    trade_date: str = "",
    limit: int = 50,
    db: Session = Depends(get_db),
) -> MarketPulseHistoryResponse:
    items = list_market_pulse_events(db, trade_date=trade_date.strip(), limit=limit)
    return MarketPulseHistoryResponse(items=items, total=len(items))


@router.get("/hourly-snapshots/history", response_model=MarketHourlySnapshotHistoryResponse)
def market_hourly_snapshot_history(
    trade_date: str = "",
    limit: int = 24,
    db: Session = Depends(get_db),
) -> MarketHourlySnapshotHistoryResponse:
    items = list_hourly_snapshot_history(db, trade_date=trade_date.strip(), limit=limit)
    return MarketHourlySnapshotHistoryResponse(items=items, total=len(items))


@router.get("/review-summary", response_model=MarketReviewSummaryResponse)
def market_review_summary(
    db: Session = Depends(get_db),
) -> MarketReviewSummaryResponse:
    status, reports = build_market_review_summary(db)
    return MarketReviewSummaryResponse(review_status=status, review_reports=reports)


@router.get("/review-history", response_model=MarketReviewHistoryResponse)
def market_review_history(
    limit: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> MarketReviewHistoryResponse:
    reports = list_market_review_history(db, limit=limit)
    return MarketReviewHistoryResponse(items=reports, total=len(reports))


def _market_breadth_response(regime, db: Session) -> MarketBreadthResponse:
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
        emotion_temperature=str(getattr(regime, "emotion_temperature", "unknown") or "unknown"),
        emotion_temperature_text=str(getattr(regime, "emotion_temperature_text", "情绪温度数据不足") or "情绪温度数据不足"),
        emotion_temperature_score=round(float(getattr(regime, "emotion_temperature_score", 0.0) or 0.0), 2),
        hot_industries=regime.hot_industries[:8],
        hot_turnover=round(regime.hot_turnover, 4),
        hot_overlap_ratio=round(regime.hot_overlap_ratio, 4),
        data_quality="fresh" if regime.breadth_ready and regime.emotion_ready else "partial",
        data_quality_text=market_regime_quality_text(regime),
        hourly_all_market_snapshot=latest_hourly_all_market_snapshot(db),
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


@router.get("/etf-universe", response_model=EtfUniverseResponse)
def etf_universe(
    category: str = Query(default="", max_length=32),
    t0_only: bool = False,
    current_user: User = Depends(get_current_user),
) -> EtfUniverseResponse:
    require_research_access(current_user)
    category_filter = _etf_category_filter(category)
    profiles = list_etf_profiles()
    if category_filter:
        profiles = [item for item in profiles if item.category == category_filter]
    if t0_only:
        profiles = [item for item in profiles if item.same_day_sell_allowed]
    items = [
        EtfUniverseProfileOut(
            symbol=item.symbol,
            name=item.name,
            category=item.category.value,
            t0_eligible=item.t0_eligible,
            settlement_rule=item.settlement_rule,
            tracking_index=item.tracking_index,
            min_amount=item.min_amount,
            max_spread_bps=item.max_spread_bps,
            slippage_bps=item.slippage_bps,
            premium_discount_available=item.premium_discount_available,
            enabled_for_t0=item.enabled_for_t0,
            same_day_sell_allowed=item.same_day_sell_allowed,
            notes=item.notes,
        )
        for item in profiles
    ]
    return EtfUniverseResponse(
        version=ETF_UNIVERSE_VERSION,
        updated_at=beijing_now_string(),
        total=len(items),
        t0_enabled_count=sum(1 for item in items if item.same_day_sell_allowed),
        items=items,
        notes=[
            "ETF universe 由代码内置基线与 market.sector_etf_t0.universe_overrides 运行时参数合并生成。",
            "该接口只暴露 T+0 eligibility 与交易约束，不生成策略信号；策略真源仍在 Python 服务层。",
            "未知行业 ETF 默认不自动提升为 T+0，必须显式写入 universe 覆盖并通过流动性、价差和数据质量检查。",
        ],
    )


@router.get("/etf-universe/admin", response_model=EtfUniverseAdminResponse)
def etf_universe_admin(
    _admin: None = Depends(require_admin_auth),
    db: Session = Depends(get_db),
) -> EtfUniverseAdminResponse:
    return EtfUniverseAdminResponse(**EtfUniverseAdminService(db).admin_payload())


@router.post("/etf-universe/validate", response_model=EtfUniverseAdminResponse)
def validate_etf_universe(
    payload: EtfUniverseValidateRequest,
    _admin: None = Depends(require_admin_auth),
    db: Session = Depends(get_db),
) -> EtfUniverseAdminResponse:
    return EtfUniverseAdminResponse(**EtfUniverseAdminService(db).admin_payload(payload.draft_overrides))


@router.post("/etf-universe/repair-draft")
def etf_universe_repair_draft(
    payload: EtfUniverseRepairDraftRequest,
    _admin: None = Depends(require_admin_auth),
    db: Session = Depends(get_db),
) -> dict:
    return EtfUniverseAdminService(db).repair_draft(symbol=payload.symbol, name=payload.name, category=payload.category)


@router.post("/etf-universe/apply", response_model=EtfUniverseMutationResponse)
def apply_etf_universe(
    payload: EtfUniverseApplyRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    _admin: None = Depends(require_admin_auth),
    db: Session = Depends(get_db),
) -> EtfUniverseMutationResponse:
    try:
        result = EtfUniverseAdminService(db).apply(
            draft_overrides=payload.draft_overrides,
            version=payload.version,
            description=payload.description,
            activate=payload.activate,
            confirm_high_risk=payload.confirm_high_risk,
            user=current_user,
            operator_ip=request.client.host if request.client else "",
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return EtfUniverseMutationResponse(**result)


@router.post("/etf-universe/rollback", response_model=EtfUniverseMutationResponse)
def rollback_etf_universe(
    payload: EtfUniverseRollbackRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    _admin: None = Depends(require_admin_auth),
    db: Session = Depends(get_db),
) -> EtfUniverseMutationResponse:
    try:
        result = EtfUniverseAdminService(db).rollback(
            version=payload.version,
            confirm=payload.confirm,
            user=current_user,
            operator_ip=request.client.host if request.client else "",
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return EtfUniverseMutationResponse(**result)


@router.get("/etf-minute-snapshots", response_model=EtfMinuteSnapshotBatchResponse)
def etf_minute_snapshots(
    symbols: str = Query(default="", max_length=1000),
    period: str = Query(default="1m", pattern="^(1m|5m|15m)$"),
    limit: int = Query(default=30, ge=1, le=240),
    current_user: User = Depends(get_current_user),
) -> EtfMinuteSnapshotBatchResponse:
    require_research_access(current_user)
    cleaned = [item.strip() for item in symbols.split(",") if item.strip()]
    if not cleaned:
        return EtfMinuteSnapshotBatchResponse(
            period=period,
            data_quality="unavailable",
            missing=[],
            notes=["symbols 为空，未查询 ETF 分钟快照。"],
        )
    response = load_go_etf_minute_snapshots(cleaned, period=period, limit=limit)
    if response is not None:
        return response
    return EtfMinuteSnapshotBatchResponse(
        period=period,
        data_quality="unavailable",
        missing=cleaned,
        notes=[
            "Go market-read-service 未配置或暂不可用，Python 策略信号仍会按原有行情服务回退。",
            "该接口只用于研究/诊断 ETF 分钟快照质量，不参与策略决策。",
        ],
    )


@router.get("/sector-relative-strength", response_model=SectorRelativeStrengthResponse)
def sector_relative_strength(
    limit: int = 8,
    per_sector_limit: int = 10,
    db: Session = Depends(get_db),
) -> SectorRelativeStrengthResponse:
    return market_data.sector_relative_strength_rank(
        db,
        limit=max(1, min(limit, 20)),
        per_sector_limit=max(1, min(per_sector_limit, 30)),
    )


def _etf_category_filter(value: str) -> EtfCategory | None:
    normalized = (value or "").strip()
    if not normalized:
        return None
    try:
        return EtfCategory(normalized)
    except ValueError:
        return None


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


@router.get("/alternative-sentiment")
def alternative_sentiment(
    symbols: str = "",
    limit: int = 80,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    require_research_access(current_user)
    symbol_list = [item.strip() for item in symbols.split(",") if item.strip()]
    return AlternativeDataSentimentService(db).build(symbols=symbol_list or None, limit=limit)


@router.get("/multi-exchange-arbitrage/research")
def multi_exchange_arbitrage_research(
    symbols: str = "",
    current_user: User = Depends(get_current_user),
) -> dict:
    require_research_access(current_user)
    symbol_list = [item.strip() for item in symbols.split(",") if item.strip()]
    return build_multi_exchange_arbitrage_research(symbol_list)


@router.get("/intraday-anomaly/{symbol}", response_model=IntradayAnomalyResponse)
def intraday_anomaly(symbol: str, db: Session = Depends(get_db)) -> IntradayAnomalyResponse:
    response = intraday_anomaly_service.detect(symbol.strip())
    intraday_anomaly_service.record_observation(db, response)
    db.commit()
    return response


@router.get("/intraday-key-levels/{symbol}", response_model=IntradayKeyLevelResponse)
def intraday_key_levels(symbol: str) -> IntradayKeyLevelResponse:
    return intraday_key_level_service.build(symbol.strip())


@router.get("/intraday-anomaly-validation", response_model=MarketModelValidationResponse)
def intraday_anomaly_validation(
    symbols: str = "510300,300059,000001,600000,002594",
    db: Session = Depends(get_db),
) -> MarketModelValidationResponse:
    symbol_list = [item.strip() for item in symbols.split(",") if item.strip()]
    response = intraday_anomaly_service.validation_report(symbol_list, db=db)
    db.commit()
    return response
