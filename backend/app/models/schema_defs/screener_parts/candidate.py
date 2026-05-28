from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from app.models.schema_defs.screener_parts.common import BuySignalState
from app.models.schema_defs.screener_parts.plans import LowBuyExitPlanOut, LowBuyHardRiskOut, LowBuyNextDayEventPlanOut

class LowBuyCandidateOut(BaseModel):
    strategy_key: str = "first_board"
    strategy_title: str = "首板回调"
    payload_version: int = 0
    symbol: str
    name: str
    market: str
    instrument_type: str
    sector_name: Optional[str] = None
    latest_price: float
    change_pct: float
    quote_timestamp: str
    data_quality: str = "ok"
    data_quality_text: str = "数据完整"
    data_quality_tags: list[str] = Field(default_factory=list)
    board_date: str
    board_count: int
    retracement_days: int
    score: float
    entry_zone_low: float
    entry_zone_high: float
    stop_loss: float
    take_profit: float
    ma5: float
    ma10: float
    ma20: float
    volume_burst_ratio: float
    volume_shrink_ratio: float
    support_distance_pct: float
    distribution_risk_score: float = 0.0
    trend_fatigue_score: float = 0.0
    false_breakout_flag: bool = False
    stall_after_volume_flag: bool = False
    intraday_reversal_flag: bool = False
    execution_ready: bool
    execution_note: str
    stage_scores: dict[str, float] = Field(default_factory=dict)
    factor_scores: dict[str, float] = Field(default_factory=dict)
    stage_text: str = ""
    risk_tier: Literal["block", "degrade", "note"] = "note"
    trigger_condition: str = ""
    invalid_condition: str = ""
    next_watch_price: Optional[float] = None
    leader_rank: str = "unknown"
    leader_strength_score: float = 0.0
    leader_strength_rank: int = 0
    leader_strength_text: str = ""
    mainline_rank: int = 0
    mainline_tier: str = "unknown"
    mainline_tier_text: str = "主线未知"
    execution_quality_score: float = 0.0
    execution_quality_text: str = ""
    dynamic_threshold_adjustment: float = 0.0
    dynamic_position_multiplier: float = 1.0
    risk_position_multiplier: float = 1.0
    industry_tier: str = "neutral"
    industry_tier_text: str = "中性行业"
    industry_position_multiplier: float = 1.0
    position_breakdown_text: str = ""
    atr_pct: float = 0.0
    atr_window: int = 14
    atr_source: str = "daily_ohlcv_true_range_14"
    volatility_position_pct: float = 0.0
    final_position_cap_pct: float = 0.0
    position_cap_reason: str = ""
    hard_risk: LowBuyHardRiskOut = Field(default_factory=LowBuyHardRiskOut)
    next_day_event_plan: LowBuyNextDayEventPlanOut = Field(default_factory=LowBuyNextDayEventPlanOut)
    exit_plan: LowBuyExitPlanOut = Field(default_factory=LowBuyExitPlanOut)
    entry_distance_pct: float = 0.0
    suggested_position_pct: float = 0.0
    suggested_position_text: str = ""
    market_state: str = "low_volume_wait"
    market_state_text: str = ""
    market_state_category: str = "low_volume_wait"
    market_state_category_text: str = "缩量无主线"
    market_state_strength: float = 0.0
    market_position_multiplier: float = 1.0
    multi_timeframe_resonance_score: float = 0.0
    multi_timeframe_resonance_text: str = ""
    confirmed_trade_date: Optional[str] = None
    summary_reason: str = ""
    buy_signal_state: BuySignalState = "watch"
    buy_signal_text: str = "继续观察"
    buy_signal_hint: str = ""
    recommendation_start_date: Optional[str] = None
    recommendation_days: int = 0
    strategy_recommendation_days: dict[str, int] = Field(default_factory=dict)
    recommendation_duration_text: str = ""
    research_stage: Literal["none", "watch", "near_entry", "buy_ready", "blocked"] = "none"
    research_stage_text: str = ""
    research_failed_rules: list[str] = Field(default_factory=list)
    research_near_miss_rules: list[str] = Field(default_factory=list)
    research_blocked_reason: str = ""
    main_force_advice: dict[str, Any] = Field(default_factory=dict)
    reasons: list[str]
    risks: list[str]
    tags: list[str]

class LowBuyQuoteRefreshOut(BaseModel):
    latest_price: float
    change_pct: float
    quote_timestamp: str
    data_source: Optional[str] = None
    source_quality: Optional[str] = None
    is_stale: bool = False
    data_quality: str = "ok"
    data_quality_text: str = "数据完整"
    data_quality_tags: list[str] = Field(default_factory=list)
    in_entry_zone: bool = False
    distance_to_entry_pct: float = 0.0
    stop_confirmed: bool = False
    suggested_position_pct: float = 0.0
    suggested_position_text: str = ""
    position_breakdown_text: str = ""
    execution_quality_score: float = 0.0
    execution_quality_text: str = ""
    buy_signal_state: BuySignalState = "watch"
    buy_signal_text: str = "继续观察"
    buy_signal_hint: str = ""
    trigger_condition: str = ""
    invalid_condition: str = ""
    risk_tier: Literal["block", "degrade", "note"] = "note"
    next_watch_price: Optional[float] = None
    atr_pct: float = 0.0
    atr_window: int = 14
    atr_source: str = "daily_ohlcv_true_range_14"
