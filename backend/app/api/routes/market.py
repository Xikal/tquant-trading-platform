from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.auth import get_current_user
from app.core.timezone import beijing_now_string
from app.models.schema_defs.market import MarketBreadthResponse
from app.services.market_data import MarketDataService

router = APIRouter(prefix="/market", dependencies=[Depends(get_current_user)])
market_data = MarketDataService()


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
        data_quality_text="实时数据" if regime.breadth_ready and regime.emotion_ready else "部分数据降级",
    )
