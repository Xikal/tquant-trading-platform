from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.models.schema_defs.analysis import StrategySuggestion
from app.models.schema_defs.common import QuoteSnapshot, TradingRuleOut
from app.models.schema_defs.screener import (
    LowBuyCandidateOut,
    LowBuyDailyDecisionOut,
    LowBuyPortfolioRiskOut,
    LowBuyPriorityFamilySectionOut,
    LowBuyPriorityBoardItemOut,
    LowBuySimpleBucketOut,
)
from app.models.schema_defs.watchlist import WatchlistCreate, WatchlistItemOut


class AppResponseMeta(BaseModel):
    updated_at: str
    is_stale: bool = False
    warnings: list[str] = Field(default_factory=list)


class AppMutationResponse(BaseModel):
    message: str
    symbol: str


class AppFeatureFlags(BaseModel):
    watchlist_enabled: bool = True
    low_buy_enabled: bool = True
    android_update_enabled: bool = True


class AppBootstrapTab(BaseModel):
    key: str
    title: str


class AppBootstrapResponse(AppResponseMeta):
    app_name: str
    app_version: str
    min_supported_version: str
    tabs: list[AppBootstrapTab]
    default_refresh_seconds: int
    market_disclaimer: str
    feature_flags: AppFeatureFlags


class AppAndroidUpdateResponse(BaseModel):
    platform: str = "android"
    current_version_code: int
    latest_version_code: int
    latest_version_name: str
    min_supported_version_code: int = 1
    update_available: bool
    mandatory: bool = False
    title: str
    message: str
    changelog: list[str] = Field(default_factory=list)
    apk_url: str
    apk_size_bytes: int = 0
    apk_sha256: str = ""
    published_at: str = ""


class AppHomeSummary(BaseModel):
    total: int = 0
    positive_t_count: int = 0
    negative_t_count: int = 0
    hold_count: int = 0
    high_risk_count: int = 0


class AppWatchlistCard(BaseModel):
    symbol: str
    name: str
    base_position: int
    available_position: int
    cost_basis: Optional[float] = None
    memo: str
    quote: QuoteSnapshot
    signal: StrategySuggestion
    rules: TradingRuleOut
    headline_reason: str = ""
    headline_blocker: str = ""
    plain_action_text: str = ""
    plain_action_reason: str = ""
    plain_execution_text: str = ""
    plain_invalid_condition: str = ""
    error: Optional[str] = None
    updated_at: str
    is_stale: bool = False


class AppHomeResponse(AppResponseMeta):
    summary: AppHomeSummary
    items: list[AppWatchlistCard] = Field(default_factory=list)


class AppWatchlistResponse(AppResponseMeta):
    items: list[WatchlistItemOut] = Field(default_factory=list)


class AppWatchlistDetailSections(BaseModel):
    reasons: list[str] = Field(default_factory=list)
    blocking_rules: list[str] = Field(default_factory=list)
    strategy_notes: str = ""


class AppWatchlistDetailResponse(AppResponseMeta):
    symbol: str
    name: str
    base_position: int
    available_position: int
    cost_basis: Optional[float] = None
    memo: str
    quote: QuoteSnapshot
    signal: StrategySuggestion
    rules: TradingRuleOut
    detail_sections: AppWatchlistDetailSections


class AppLowBuyStrategySummary(BaseModel):
    strategy_key: str
    strategy_title: str
    strategy_subtitle: str = ""
    strategy_logic: str = ""


class AppLowBuySummary(BaseModel):
    as_of_date: str
    latest_trade_date: str
    pool_size: int = 0
    scanned_count: int = 0
    matched_count: int = 0
    full_scan_ready: bool = False
    full_scan_in_progress: bool = False


class AppLowBuyPriorityBoard(BaseModel):
    as_of_date: str = ""
    latest_trade_date: str = ""
    updated_at: str = ""
    total_candidates: int = 0
    immediate_count: int = 0
    focus_count: int = 0
    track_count: int = 0
    market_state: str = "neutral"
    market_state_text: str = ""
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
    family_sections: list[LowBuyPriorityFamilySectionOut] = Field(default_factory=list)
    daily_decision: LowBuyDailyDecisionOut = Field(default_factory=LowBuyDailyDecisionOut)
    simple_buckets: list[LowBuySimpleBucketOut] = Field(default_factory=list)
    items: list[LowBuyPriorityBoardItemOut] = Field(default_factory=list)


class AppLowBuyResponse(AppResponseMeta):
    strategy: AppLowBuyStrategySummary
    summary: AppLowBuySummary
    priority_board: AppLowBuyPriorityBoard
    confirmed_candidates: list[LowBuyCandidateOut] = Field(default_factory=list)
    watch_candidates: list[LowBuyCandidateOut] = Field(default_factory=list)


class AppFavoriteStatus(BaseModel):
    in_watchlist: bool
    watchlist_symbol: Optional[str] = None


class AppLowBuyDetailResponse(AppResponseMeta):
    candidate: LowBuyCandidateOut
    favorite_status: AppFavoriteStatus


class AppLowBuyFavoriteRequest(BaseModel):
    name: str = ""
    base_position: int = 1000
    available_position: int = 1000
    cost_basis: Optional[float] = None
    memo: str = "来自选股宝典"


AppWatchlistUpsertRequest = WatchlistCreate
