from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class StrategyTrackingSummaryOut(BaseModel):
    tracking_count: int = 0
    active_count: int = 0
    today_new_count: int = 0
    in_entry_zone_count: int = 0
    stopped_count: int = 0
    needs_review_count: int = 0
    abnormal_return_count: int = 0
    shadow_observation_count: int = 0
    avg_current_return_pct: float = 0.0
    median_max_gain_pct: float = 0.0
    data_quality: str = "unavailable"
    data_quality_text: str = "暂无可跟踪推荐"
    generated_at: str = ""


class StrategyTrackingPerformanceOut(BaseModel):
    strategy_key: str
    strategy_name: str = ""
    strategy_family: str = ""
    recommendation_count: int = 0
    entry_touched_count: int = 0
    entry_touch_rate: float = 0.0
    win_rate_3d: float = 0.0
    win_rate_5d: float = 0.0
    win_rate_10d: float = 0.0
    avg_current_return_pct: float = 0.0
    avg_max_gain_pct: float = 0.0
    avg_max_drawdown_pct: float = 0.0
    profit_loss_ratio: float = 0.0
    stop_loss_rate: float = 0.0
    active_count: int = 0
    health_score: int = 0
    health_grade: str = "insufficient_sample"
    sample_quality: str = "insufficient"
    health_reasons: list[str] = Field(default_factory=list)
    health_risks: list[str] = Field(default_factory=list)


class StrategyTrackingSegmentOut(BaseModel):
    strategy_key: str = ""
    strategy_name: str = ""
    market_state: str = "unknown"
    market_state_text: str = "市场状态不足"
    sector_state: str = "sector_unknown"
    sector_state_text: str = "板块状态不足"
    recommendation_count: int = 0
    entry_touch_rate: float = 0.0
    win_rate_5d: float = 0.0
    avg_max_gain_pct: float = 0.0
    avg_max_drawdown_pct: float = 0.0
    stop_loss_rate: float = 0.0
    return_drawdown_ratio: float = 0.0


class StrategyTrackingShadowObservationOut(BaseModel):
    model_key: str
    model_version: str = ""
    observation_count: int = 0
    latest_observed_at: str | None = None
    linked_tracking_count: int = 0
    no_sample_reason: str = ""
    no_sample_reason_text: str = ""
    actionable_count: int = 0
    settled_count: int = 0
    success_rate_pct: float = 0.0


class StrategyTrackingItemOut(BaseModel):
    id: str
    symbol: str
    name: str = ""
    strategy_key: str
    strategy_name: str = ""
    strategy_family: str = ""
    signal_state: str = ""
    signal_text: str = ""
    observe_only: bool = False
    lifecycle_status: str = "data_unavailable"
    lifecycle_status_text: str = "数据不足"
    first_signal_date: str = ""
    latest_signal_date: str = ""
    first_signal_price: float | None = None
    entry_zone_low: float | None = None
    entry_zone_high: float | None = None
    stop_loss: float | None = None
    target_price: float | None = None
    current_price: float | None = None
    latest_trade_date: str = ""
    recommendation_days: int = 0
    distance_to_entry_pct: float | None = None
    current_return_pct: float | None = None
    max_price_after_signal: float | None = None
    max_gain_pct: float | None = None
    max_drawdown_pct: float | None = None
    actual_low_price: float | None = None
    actual_low_date: str | None = None
    actual_high_date: str | None = None
    spike_retrace_pct: float | None = None
    best_holding_days: int = 0
    best_exit_date: str | None = None
    best_exit_return_pct: float | None = None
    best_exit_drawdown_pct: float | None = None
    return_drawdown_ratio: float | None = None
    giveback_from_peak_pct: float | None = None
    holding_bucket: str = "unavailable"
    exit_quality: str = "unavailable"
    exit_reason: str = ""
    hold_extension_state: str = "unavailable"
    hold_extension_text: str = "数据不足"
    hold_extension_score: int = 0
    hold_extension_reasons: list[str] = Field(default_factory=list)
    hold_extension_risks: list[str] = Field(default_factory=list)
    suggested_holding_plan: str = "unavailable"
    entry_touched: bool = False
    stop_triggered: bool = False
    stop_triggered_date: str | None = None
    target_touched: bool = False
    target_touched_date: str | None = None
    invalidated_date: str | None = None
    conclusion: str = ""
    failure_reason: str = ""
    failure_tags: list[str] = Field(default_factory=list)
    failure_reason_text: str = ""
    market_state: str = "unknown"
    market_state_text: str = "市场状态不足"
    sector_state: str = "sector_unknown"
    sector_state_text: str = "板块状态不足"
    signal_generated_at: str = ""
    data_cutoff_at: str = ""
    lookback_start_date: str = ""
    lookback_end_date: str = ""
    posterior_start_date: str = ""
    posterior_end_date: str = ""
    market_data_source: str = ""
    market_data_updated_at: str = ""
    future_leak_check: str = "passed"
    audit_flags: list[str] = Field(default_factory=list)
    abnormal_return: bool = False
    needs_review: bool = False
    review_priority: str = "normal"
    review_text: str = ""
    data_quality: str = "unavailable"
    data_quality_text: str = "行情数据不足"
    source: str = "low_buy_result_snapshot"
    detail_available: bool = True


class StrategyTrackingTimelinePointOut(BaseModel):
    trade_date: str
    open: float
    high: float
    low: float
    close: float
    pct_chg: float = 0.0
    current_return_pct: float | None = None
    max_return_pct: float | None = None
    max_drawdown_pct: float | None = None
    holding_day: int = 0
    is_best_exit: bool = False
    hold_extension_state: str = "unavailable"
    hit_entry_zone: bool = False
    hit_stop_loss: bool = False
    hit_target: bool = False
    lifecycle_status: str = "active"
    data_quality: str = "ok"


class StrategyTrackingMarkerOut(BaseModel):
    kind: str
    trade_date: str
    price: float | None = None
    label: str = ""


class StrategyTrackingListResponse(BaseModel):
    items: list[StrategyTrackingItemOut] = Field(default_factory=list)
    total: int = 0
    limit: int = 30
    offset: int = 0
    sort: str = "max_gain_desc"
    summary: StrategyTrackingSummaryOut = Field(default_factory=StrategyTrackingSummaryOut)
    performance: list[StrategyTrackingPerformanceOut] = Field(default_factory=list)
    market_segments: list[StrategyTrackingSegmentOut] = Field(default_factory=list)
    shadow_observations: list[StrategyTrackingShadowObservationOut] = Field(default_factory=list)
    partial_errors: list[str] = Field(default_factory=list)
    production_writeable: bool = False
    read_path: str = "python_read_through_go_boundary_reserved"
    rust_math_used: bool = True
    notes: list[str] = Field(default_factory=list)


class StrategyTrackingDetailResponse(BaseModel):
    item: StrategyTrackingItemOut
    timeline: list[StrategyTrackingTimelinePointOut] = Field(default_factory=list)
    markers: list[StrategyTrackingMarkerOut] = Field(default_factory=list)
    signal_snapshot: dict[str, Any] = Field(default_factory=dict)
    review_text: str = ""
    partial_errors: list[str] = Field(default_factory=list)
    production_writeable: bool = False


class StrategyTrackingReviewResponse(BaseModel):
    summary: StrategyTrackingSummaryOut = Field(default_factory=StrategyTrackingSummaryOut)
    performance: list[StrategyTrackingPerformanceOut] = Field(default_factory=list)
    market_segments: list[StrategyTrackingSegmentOut] = Field(default_factory=list)
    failure_tags: dict[str, int] = Field(default_factory=dict)
    needs_review_items: list[StrategyTrackingItemOut] = Field(default_factory=list)
    abnormal_return_items: list[StrategyTrackingItemOut] = Field(default_factory=list)


class StrategyTrackingReportOut(BaseModel):
    report_type: str = "daily"
    generated_at: str = ""
    window_start: str = ""
    window_end: str = ""
    data_quality: str = "unavailable"
    summary: StrategyTrackingSummaryOut = Field(default_factory=StrategyTrackingSummaryOut)
    new_signals: list[StrategyTrackingItemOut] = Field(default_factory=list)
    entry_touched: list[StrategyTrackingItemOut] = Field(default_factory=list)
    stopped: list[StrategyTrackingItemOut] = Field(default_factory=list)
    spike_retraced: list[StrategyTrackingItemOut] = Field(default_factory=list)
    abnormal_returns: list[StrategyTrackingItemOut] = Field(default_factory=list)
    shadow_observations: list[StrategyTrackingShadowObservationOut] = Field(default_factory=list)
    markdown: str = ""


class StrategyTrackingRefreshResponse(BaseModel):
    ok: bool = True
    storage_mode: str = "read_through_view"
    refreshed_count: int = 0
    changed_strategy_results: bool = False
    changed_paper_ledger: bool = False
    summary: StrategyTrackingSummaryOut = Field(default_factory=StrategyTrackingSummaryOut)
