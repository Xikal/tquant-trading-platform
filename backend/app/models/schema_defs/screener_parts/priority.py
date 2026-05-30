from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from app.models.schema_defs.screener_parts.common import BuySignalState
from app.models.schema_defs.screener_parts.plans import LowBuyNextDayEventPlanOut, LowBuyPortfolioRiskOut

class LowBuyPriorityBoardItemOut(BaseModel):
    symbol: str
    name: str
    sector_name: Optional[str] = None
    strategy_key: str
    strategy_title: str
    strategy_titles: list[str] = Field(default_factory=list)
    strategy_count: int = 1
    family_count: int = 1
    strategy_family: str = "uncategorized"
    strategy_family_text: str = "未分类策略"
    latest_price: float
    change_pct: float
    quote_timestamp: str
    data_quality: str = "ok"
    data_quality_text: str = "数据完整"
    data_quality_tags: list[str] = Field(default_factory=list)
    market_gate_decision: str = "allow"
    market_gate_score: float = 100.0
    market_gate_reasons: list[str] = Field(default_factory=list)
    market_firepower_multiplier: float = 1.0
    market_state_category: str = "low_volume_wait"
    market_state_category_text: str = "缩量无主线"
    buy_signal_state: BuySignalState = "watch"
    buy_signal_text: str = "继续观察"
    priority_score: float = 0.0
    strategy_weight_score: float = 0.0
    industry_rotation_bonus: float = 0.0
    industry_rotation_text: str = ""
    industry_tier: str = "neutral"
    industry_tier_text: str = "中性行业"
    industry_position_multiplier: float = 1.0
    position_breakdown_text: str = ""
    action_summary: str = ""
    blocked_reason: str = ""
    trigger_condition: str = ""
    invalid_condition: str = ""
    risk_tier: Literal["block", "degrade", "note"] = "note"
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
    strategy_performance_text: str = ""
    kelly_half_position_pct: float = 0.0
    kelly_position_text: str = ""
    atr_pct: float = 0.0
    atr_window: int = 14
    atr_source: str = "daily_ohlcv_true_range_14"
    volatility_position_pct: float = 0.0
    final_position_cap_pct: float = 0.0
    position_cap_reason: str = ""
    next_day_event_plan: LowBuyNextDayEventPlanOut = Field(default_factory=LowBuyNextDayEventPlanOut)
    multi_timeframe_resonance_score: float = 0.0
    multi_timeframe_resonance_text: str = ""
    entry_zone_low: float
    entry_zone_high: float
    stop_loss: float
    suggested_position_pct: float = 0.0
    suggested_position_text: str = ""
    recommendation_start_date: Optional[str] = None
    recommendation_days: int = 0
    strategy_recommendation_days: dict[str, int] = Field(default_factory=dict)
    recommendation_duration_text: str = ""
    simple_bucket: Literal["buy_now", "wait_price", "give_up"] = "give_up"
    simple_bucket_text: str = "放弃观察"
    next_action_text: str = ""
    exit_plan_text: str = ""
    main_force_advice: dict[str, Any] = Field(default_factory=dict)
    main_force_rank_bonus: float = 0.0
    production_score: Optional[float] = None
    watch_score: Optional[float] = None
    production_decision: str = ""
    front_row_tier: str = "unknown"
    score_cap: Optional[float] = None
    score_components: dict[str, float] = Field(default_factory=dict)
    exclusion_reasons: list[str] = Field(default_factory=list)
    warning_tags: list[str] = Field(default_factory=list)
    production_scoring_config_version: str = ""
    strategy_variant: str = "baseline"
    strategy_role: str = "production_baseline"
    display_lane: str = "baseline"
    display_lane_title: str = "原低吸策略"
    display_lane_subtitle: str = ""
    production_sort_replaced: bool = False
    production_enabled: bool = True
    paper_enabled: bool = False
    watch_only: bool = False
    matched_strategy_variants: list[str] = Field(default_factory=list)
    primary_lane_reason: str = ""
    elite_watch_score: Optional[float] = None
    readiness_status: str = ""
    readiness_blockers: list[str] = Field(default_factory=list)

class LowBuyPriorityFamilyPerformanceOut(BaseModel):
    family_key: str
    family_text: str
    strategy_count: int = 0
    evaluated_signals: int = 0
    filled_signals: int = 0
    not_filled_signals: int = 0
    hit_count: int = 0
    net_win_rate: float = 0.0
    avg_net_return_pct: float = 0.0
    not_filled_rate: float = 0.0
    stop_loss_rate: float = 0.0
    hit_rate: float = 0.0

class LowBuyPriorityFamilySectionOut(BaseModel):
    family_key: str
    family_text: str
    total_candidates: int = 0
    immediate_count: int = 0
    focus_count: int = 0
    track_count: int = 0
    avg_priority_score: float = 0.0
    top_strategy_titles: list[str] = Field(default_factory=list)
    performance: Optional[LowBuyPriorityFamilyPerformanceOut] = None
    items: list[LowBuyPriorityBoardItemOut] = Field(default_factory=list)

class LowBuyDailyDecisionOut(BaseModel):
    key: Literal["tradable", "observe_only", "wait"] = "wait"
    title: str = "空仓等待"
    message: str = "今天不适合新开仓，优先处理持仓或空仓等待。"
    market_plain_text: str = ""
    risk_level: Literal["low", "medium", "high"] = "medium"
    action_steps: list[str] = Field(default_factory=list)

class LowBuySimpleBucketOut(BaseModel):
    key: Literal["buy_now", "wait_price", "give_up"] = "give_up"
    title: str
    description: str = ""
    count: int = 0
    symbols: list[str] = Field(default_factory=list)

class LowBuyPriorityBoardResponse(BaseModel):
    strategy_variant: str = "baseline"
    display_lane: str = "baseline"
    display_lane_title: str = "原低吸策略"
    display_lane_subtitle: str = ""
    production_sort_replaced: bool = False
    lane_summary: dict[str, Any] = Field(default_factory=dict)
    available_lanes: list[dict[str, Any]] = Field(default_factory=list)
    readiness_summary: dict[str, Any] = Field(default_factory=dict)
    as_of_date: str
    latest_trade_date: str
    latest_available_trade_date: str = ""
    snapshot_warning: str = ""
    updated_at: str
    total_candidates: int = 0
    immediate_count: int = 0
    focus_count: int = 0
    track_count: int = 0
    market_state: str = "neutral"
    market_state_text: str = ""
    market_state_category: str = "low_volume_wait"
    market_state_category_text: str = "缩量无主线"
    data_quality: str = "ok"
    data_quality_text: str = "数据完整"
    data_quality_tags: list[str] = Field(default_factory=list)
    market_gate_decision: str = "allow"
    market_gate_score: float = 100.0
    market_gate_reasons: list[str] = Field(default_factory=list)
    market_firepower_multiplier: float = 1.0
    directional_bias: str = "neutral"
    directional_bias_text: str = "观望"
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
    missing_strategies: list[str] = Field(default_factory=list)
    stale_strategies: list[str] = Field(default_factory=list)
    family_sections: list[LowBuyPriorityFamilySectionOut] = Field(default_factory=list)
    daily_decision: LowBuyDailyDecisionOut = Field(default_factory=LowBuyDailyDecisionOut)
    simple_buckets: list[LowBuySimpleBucketOut] = Field(default_factory=list)
    items: list[LowBuyPriorityBoardItemOut] = Field(default_factory=list)
