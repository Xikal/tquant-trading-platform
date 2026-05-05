from __future__ import annotations

from typing import Any, Literal, Optional

BuySignalState = Literal["buy_now", "soft_buy_now", "near_entry", "watch", "avoid"]

from pydantic import BaseModel, Field


class LowBuyStrategyGovernanceItemOut(BaseModel):
    strategy_key: str
    strategy_title: str
    subtitle: str = ""
    tier: Literal["core", "auxiliary", "research", "factor"] = "research"
    layer: Literal["production", "research", "factor"] = "research"
    status: Literal["active", "watch", "paused", "research", "deprecated"] = "research"
    status_text: str = ""
    enabled: bool = True
    participates_priority_board: bool = False
    strong_buy_paused: bool = True
    requires_mainline_industry: bool = False
    pool_key: str = ""
    pool_title: str = ""
    pool_source: str = ""
    pool_max_size: int = 0
    uses_daily_scan_pool: bool = False
    max_holding_days: int = 0
    holding_brief: str = ""
    strategy_health_score: float = 0.0
    strategy_health_text: str = "暂无绩效样本"
    auto_governance_status: str = ""
    auto_governance_reason: str = ""
    auto_governance_updated_at: str = ""
    performance_sample_count: int = 0
    notes: list[str] = Field(default_factory=list)


class LowBuyStrategyGovernanceResponse(BaseModel):
    default_strategy: str
    production_strategies: list[str] = Field(default_factory=list)
    items: list[LowBuyStrategyGovernanceItemOut] = Field(default_factory=list)


class LowBuyStrategyGovernanceUpdate(BaseModel):
    status: Literal["active", "watch", "paused"]
    reason: str = ""


class LowBuyExitPlanOut(BaseModel):
    stop_loss: float = 0.0
    first_take_profit: float = 0.0
    trailing_stop: float = 0.0
    max_holding_days: int = 5
    time_stop_text: str = ""
    invalid_condition: str = ""
    exit_rules: list[str] = Field(default_factory=list)


class LowBuyHardRiskOut(BaseModel):
    level: Literal["clear", "note", "degrade", "block"] = "clear"
    score_penalty: float = 0.0
    execution_blocked: bool = False
    reasons: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class LowBuyNextDayEventPlanOut(BaseModel):
    state: Literal[
        "none",
        "watch",
        "near_entry",
        "weak_to_strong_candidate",
        "take_profit_watch",
        "failed_confirmation",
    ] = "none"
    state_text: str = ""
    next_day_action: str = ""
    t2_action: str = ""
    first_take_profit_pct: float = 0.0
    second_take_profit_pct: float = 0.0
    max_holding_days: int = 0
    position_pct: float = 0.0
    confirmation_rules: list[str] = Field(default_factory=list)
    exit_rules: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)


class LowBuyPortfolioRiskOut(BaseModel):
    total_planned_position_pct: float = 0.0
    holding_position_pct: float = 0.0
    max_single_position_pct: float = 0.0
    active_signal_count: int = 0
    holding_signal_count: int = 0
    industry_concentration_pct: float = 0.0
    top_industry: str = ""
    recommended_total_cap_pct: float = 0.0
    risk_level: Literal["clear", "note", "degrade", "block"] = "clear"
    notes: list[str] = Field(default_factory=list)


class LowBuyExecutionBacktestItemOut(BaseModel):
    symbol: str
    name: str
    strategy_key: str
    signal_trade_date: str
    entry_trade_date: Optional[str] = None
    exit_trade_date: Optional[str] = None
    status: Literal["filled", "not_filled", "invalid"] = "not_filled"
    entry_price: float = 0.0
    exit_price: float = 0.0
    net_return_pct: float = 0.0
    max_gain_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    exit_reason: str = ""
    data_quality: str = "ok"
    data_quality_text: str = "数据完整"
    data_quality_tags: list[str] = Field(default_factory=list)


class LowBuyExecutionBacktestResponse(BaseModel):
    strategy_key: str
    lookback_days: int
    evaluated_signals: int = 0
    filled_signals: int = 0
    not_filled_signals: int = 0
    invalid_signals: int = 0
    win_rate: float = 0.0
    net_win_rate: float = 0.0
    not_filled_rate: float = 0.0
    stop_loss_count: int = 0
    stop_loss_rate: float = 0.0
    take_profit_count: int = 0
    take_profit_rate: float = 0.0
    time_exit_count: int = 0
    time_exit_rate: float = 0.0
    avg_net_return_pct: float = 0.0
    avg_max_gain_pct: float = 0.0
    avg_max_drawdown_pct: float = 0.0
    max_adverse_pct: float = 0.0
    avg_loss_pct: float = 0.0
    win_loss_ratio: float = 0.0
    profit_factor: float = 0.0
    data_quality: str = "ok"
    data_quality_text: str = "数据完整"
    data_quality_tags: list[str] = Field(default_factory=list)
    pbo: Optional[dict[str, Any]] = None
    crisis_scenario: Optional[dict[str, Any]] = None
    notes: list[str] = Field(default_factory=list)
    items: list[LowBuyExecutionBacktestItemOut] = Field(default_factory=list)


class LowBuyTradeLifecycleOut(BaseModel):
    symbol: str
    name: str = ""
    strategy_key: str
    signal_trade_date: str
    status: Literal["planned", "entered", "holding", "exited", "invalid"] = "planned"
    signal_state: BuySignalState = "watch"
    entry_plan_low: float = 0.0
    entry_plan_high: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    max_holding_days: int = 5
    entry_price: Optional[float] = None
    entry_trade_date: Optional[str] = None
    exit_price: Optional[float] = None
    exit_trade_date: Optional[str] = None
    exit_reason: str = ""
    realized_return_pct: float = 0.0
    max_gain_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    attribution_note: str = ""
    updated_at: str = ""


class LowBuyTradeLifecycleUpdate(BaseModel):
    signal_trade_date: str = Field(..., min_length=1)
    strategy_key: str = "first_board"
    status: Optional[Literal["planned", "entered", "holding", "exited", "invalid"]] = None
    entry_price: Optional[float] = None
    entry_trade_date: Optional[str] = None
    exit_price: Optional[float] = None
    exit_trade_date: Optional[str] = None
    exit_reason: Optional[str] = None
    realized_return_pct: Optional[float] = None
    max_gain_pct: Optional[float] = None
    max_drawdown_pct: Optional[float] = None
    attribution_note: Optional[str] = None


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


class LowBuyPerformanceBucketOut(BaseModel):
    label: str
    sample_count: int
    hit_count: int
    hit_rate: float
    avg_return_3d: float
    avg_return_5d: float


class LowBuyStrategyPerformanceOut(BaseModel):
    snapshot_version: int = 0
    lookback_days: int = 0
    signal_count: int = 0
    evaluated_signals: int = 0
    filled_signals: int = 0
    not_filled_signals: int = 0
    pending_signals: int = 0
    hit_count: int = 0
    hit_rate: float = 0.0
    net_win_rate: float = 0.0
    not_filled_rate: float = 0.0
    stop_loss_rate: float = 0.0
    avg_net_return_pct: float = 0.0
    avg_win_pct: float = 0.0
    avg_loss_pct: float = 0.0
    profit_factor: float = 0.0
    cvar_5pct: float = 0.0
    kelly_half_position_pct: float = 0.0
    win_rate_1d: float = 0.0
    win_rate_2d: float = 0.0
    win_rate_3d: float = 0.0
    win_rate_4d: float = 0.0
    win_rate_5d: float = 0.0
    avg_return_1d: float = 0.0
    avg_return_2d: float = 0.0
    avg_return_3d: float = 0.0
    avg_return_4d: float = 0.0
    avg_return_5d: float = 0.0
    avg_max_gain_5d: float = 0.0
    avg_max_drawdown_5d: float = 0.0
    target_profit_pct: float = 0.0
    updated_at: str = ""
    data_insufficient: bool = False
    attribution_notes: list[str] = Field(default_factory=list)
    sector_attribution: list["LowBuyPerformanceBucketOut"] = Field(default_factory=list)
    retracement_attribution: list["LowBuyPerformanceBucketOut"] = Field(default_factory=list)
    market_state_attribution: list["LowBuyPerformanceBucketOut"] = Field(default_factory=list)
    industry_tier_attribution: list["LowBuyPerformanceBucketOut"] = Field(default_factory=list)


class LowBuyCloseReviewItemOut(BaseModel):
    symbol: str
    name: str
    signal_state: BuySignalState = "watch"
    signal_text: str = "继续观察"
    review_trade_date: str
    close_price: float
    change_pct: float
    amplitude_pct: float
    entry_zone_low: float
    entry_zone_high: float
    stop_loss: float
    entry_distance_pct: float = 0.0
    entry_distance_text: str = ""
    close_vs_stop_pct: float = 0.0
    review_level: Literal["good", "neutral", "risk"] = "neutral"
    review_text: str = ""


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
    mainline_rank: int = 0
    mainline_tier: str = "unknown"
    mainline_tier_text: str = "主线未知"
    execution_quality_score: float = 0.0
    execution_quality_text: str = ""
    strategy_performance_text: str = ""
    next_day_event_plan: LowBuyNextDayEventPlanOut = Field(default_factory=LowBuyNextDayEventPlanOut)
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
