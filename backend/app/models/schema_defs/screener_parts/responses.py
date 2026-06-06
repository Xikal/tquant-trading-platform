from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from app.models.schema_defs.screener_parts.candidate import LowBuyCandidateOut
from app.models.schema_defs.screener_parts.performance import LowBuyCloseReviewItemOut, LowBuyStrategyPerformanceOut
from app.models.schema_defs.screener_parts.plans import LowBuyPortfolioRiskOut

class LowBuyHistorySectionOut(BaseModel):
    title: str
    description: str
    candidates: list[LowBuyCandidateOut]

class LowBuyHistoryResponse(BaseModel):
    as_of_date: str
    latest_trade_date: str
    history_sections: list[LowBuyHistorySectionOut] = Field(default_factory=list)

class LowBuyScreenerResponse(BaseModel):
    strategy_key: str = "first_board"
    strategy_title: str = "首板回调"
    strategy_subtitle: str = ""
    strategy_logic: str = ""
    requested_mode: Literal["quick", "full"] = "quick"
    response_mode: Literal["quick", "full"] = "quick"
    as_of_date: str
    latest_trade_date: str
    pool_size: int
    scanned_count: int
    matched_count: int
    snapshot_warning: str = ""
    stale: bool = False
    stale_reason: str = ""
    requested_scan_limit: int = 0
    active_scan_limit: int = 0
    full_scan_ready: bool = False
    full_scan_in_progress: bool = False
    full_scan_updated_at: Optional[str] = None
    market_state: str = "low_volume_wait"
    market_state_text: str = ""
    market_state_category: str = "low_volume_wait"
    market_state_category_text: str = "缩量无主线"
    data_quality: str = "ok"
    data_quality_text: str = "数据完整"
    data_quality_tags: list[str] = Field(default_factory=list)
    market_bonus: float = 0.0
    market_state_strength: float = 0.0
    regime_confidence: float = 0.0
    state_persistence_days: int = 1
    transition_risk: float = 0.0
    breadth_ready: bool = False
    emotion_ready: bool = False
    stock_up_ratio: float = 0.0
    stock_median_change: float = 0.0
    style_divergence: float = 0.0
    hot_turnover: float = 0.0
    hot_overlap_ratio: float = 0.0
    limit_down_count: Optional[int] = None
    limit_up_count: int = 0
    board_height: int = 0
    previous_board_height: int = 0
    promotion_ratio: float = 0.0
    broken_board_ratio: float = 0.0
    promotion_break_gap: float = 0.0
    promotion_break_pressure: float = 0.0
    high_flyer_retreat_ratio: float = 0.0
    high_flyer_gap_speed: float = 0.0
    distribution_pressure: float = 0.0
    emotion_temperature: str = "unknown"
    emotion_temperature_text: str = "情绪温度数据不足"
    emotion_temperature_score: float = 0.0
    hot_industries: list[str] = Field(default_factory=list)
    hot_industry_source: str = ""
    hot_industry_source_text: str = ""
    mainline_lifecycle_state: str = ""
    mainline_lifecycle_text: str = ""
    portfolio_risk: LowBuyPortfolioRiskOut = Field(default_factory=LowBuyPortfolioRiskOut)
    retracement_distribution: dict[str, int]
    filters: dict[str, Any]
    strategy_notes: list[str]
    performance: Optional[LowBuyStrategyPerformanceOut] = None
    close_review_trade_date: Optional[str] = None
    close_review_updated_at: Optional[str] = None
    close_review_items: list[LowBuyCloseReviewItemOut] = Field(default_factory=list)
    confirmed_candidates: list[LowBuyCandidateOut] = Field(default_factory=list)
    history_sections: list[LowBuyHistorySectionOut] = Field(default_factory=list)
    candidates: list[LowBuyCandidateOut]
