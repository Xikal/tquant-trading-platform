from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from app.models.schema_defs.common import KlineBar

DataQualityState = Literal["fresh", "stale", "partial", "unavailable"]


class IntradayMarketPulse(BaseModel):
    updated_at: str
    data_quality: DataQualityState = "unavailable"
    data_quality_text: str = "盘中 pulse 暂不可用"
    market_strength_text: str = "市场强弱待确认"
    leader_strength_text: str = "龙头强度待确认"
    emotion_text: str = "情绪温度待确认"
    hourly_snapshot_text: str = "小时快照待确认"
    pulse_level: str = "unknown"
    pulse_text: str = "等待盘中数据刷新。"
    suggested_action: str = "只读观察，不触发交易。"
    partial_errors: list[dict[str, str]] = Field(default_factory=list)
    market_breadth_summary: dict[str, Any] = Field(default_factory=dict)
    leader_strength_summary: dict[str, Any] = Field(default_factory=dict)
    emotion_summary: dict[str, Any] = Field(default_factory=dict)
    hourly_snapshot_summary: dict[str, Any] = Field(default_factory=dict)
    autofill_details: list[dict[str, Any]] = Field(default_factory=list)


class MarketHourlySnapshotHistoryOut(BaseModel):
    id: int = 0
    trade_date: str = ""
    snapshot_bucket: str = ""
    data_quality: DataQualityState = "unavailable"
    snapshot_count: int = 0
    market_strength_score: float = 0.0
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""


class MarketPulseEventOut(BaseModel):
    id: int = 0
    trade_date: str = ""
    pulse_level: str = "unknown"
    data_quality: DataQualityState = "unavailable"
    pulse_text: str = ""
    suggested_action: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: str = ""


class MarketPulseHistoryResponse(BaseModel):
    items: list[MarketPulseEventOut] = Field(default_factory=list)
    total: int = 0


class MarketHourlySnapshotHistoryResponse(BaseModel):
    items: list[MarketHourlySnapshotHistoryOut] = Field(default_factory=list)
    total: int = 0


class MarketReviewReportOut(BaseModel):
    id: int = 0
    report_date: str = ""
    report_slot: str = ""
    review_subject: str = "全市场"
    source_scope: str = "market"
    overall_summary: str = ""
    strategy_highlights: list[dict[str, Any]] = Field(default_factory=list)
    risk_alerts: list[dict[str, Any]] = Field(default_factory=list)
    suggestion: str = ""
    generated_at: str = ""
    llm_model: str = "market-rule"
    missing_data: list[dict[str, Any]] = Field(default_factory=list)
    autofill_details: list[dict[str, Any]] = Field(default_factory=list)


class MarketReviewStatusOut(BaseModel):
    trade_date: str = ""
    status: str = "empty"
    status_text: str = "今日暂无市场复盘"
    review_subject: str = "全市场"
    source_scope: str = "market"
    has_midday: bool = False
    has_close: bool = False
    next_trigger_at: str = ""
    risk_alert_count: int = 0
    suggested_action: str = "等待午盘或收盘市场复盘生成。"


class MarketReviewSummaryResponse(BaseModel):
    review_status: MarketReviewStatusOut
    review_reports: list[MarketReviewReportOut] = Field(default_factory=list)


class MarketReviewHistoryResponse(BaseModel):
    items: list[MarketReviewReportOut] = Field(default_factory=list)
    total: int = 0


class MarketBreadthResponse(BaseModel):
    updated_at: str
    state: str = ""
    state_text: str = ""
    breadth_ready: bool = False
    emotion_ready: bool = False
    stock_up_ratio: float = 0.0
    stock_median_change: float = 0.0
    largecap_change: float = 0.0
    smallcap_change: float = 0.0
    style_divergence: float = 0.0
    limit_up_count: int = 0
    limit_down_count: Optional[int] = None
    broken_board_ratio: float = 0.0
    promotion_ratio: float = 0.0
    board_height: int = 0
    emotion_temperature: str = "unknown"
    emotion_temperature_text: str = "情绪温度数据不足"
    emotion_temperature_score: float = 0.0
    hot_industries: list[str] = Field(default_factory=list)
    hot_turnover: float = 0.0
    hot_overlap_ratio: float = 0.0
    data_quality: DataQualityState = "fresh"
    data_quality_text: str = ""
    hourly_all_market_snapshot: dict = Field(default_factory=dict)
    autofill_details: list[dict[str, Any]] = Field(default_factory=list)


class MarketTradingSessionResponse(BaseModel):
    updated_at: str
    is_trading_day: bool = False
    is_trading_now: bool = False
    current_time: str = ""
    timezone: str = "Asia/Shanghai"
    data_quality_text: str = ""


class SectorRelativeStrengthItem(BaseModel):
    sector_name: str
    symbol: str
    name: str = ""
    latest_price: float = 0.0
    change_pct: float = 0.0
    sector_median_change_pct: float = 0.0
    relative_strength_ratio: float | None = None
    volume_ratio: float = 0.0
    turnover_proxy: float = 0.0
    leader_score: float = 0.0
    rank: int = 0
    data_quality_text: str = ""


class SectorRelativeStrengthResponse(BaseModel):
    updated_at: str
    trade_date: str = ""
    sector_count: int = 0
    items: list[SectorRelativeStrengthItem] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class IntradayKeyLevelOut(BaseModel):
    level_type: str
    level_text: str
    price: float
    distance_pct: float = 0.0
    alert: bool = False


class IntradayKeyLevelResponse(BaseModel):
    symbol: str
    name: str = ""
    updated_at: str
    latest_price: float = 0.0
    vwap: float = 0.0
    entry_zone_low: float | None = None
    entry_zone_high: float | None = None
    alert_threshold_pct: float = 0.3
    alert_triggered: bool = False
    alert_text: str = ""
    levels: list[IntradayKeyLevelOut] = Field(default_factory=list)
    data_quality_text: str = ""


class EtfUniverseProfileOut(BaseModel):
    symbol: str
    name: str
    category: str
    t0_eligible: bool = False
    settlement_rule: str = "t1"
    tracking_index: str = ""
    min_amount: float = 0.0
    max_spread_bps: float = 0.0
    slippage_bps: float = 0.0
    premium_discount_available: bool = False
    enabled_for_t0: bool = False
    same_day_sell_allowed: bool = False
    notes: str = ""


class EtfUniverseResponse(BaseModel):
    version: str
    updated_at: str
    total: int = 0
    t0_enabled_count: int = 0
    source: str = "runtime_quant_parameters"
    audit_scope: str = "market.sector_etf_t0.universe_overrides"
    items: list[EtfUniverseProfileOut] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class EtfUniverseAdminProfileOut(EtfUniverseProfileOut):
    source: Literal["baseline", "override"] = "baseline"
    validation_severity: Literal["ok", "info", "warning", "error"] = "ok"


class EtfUniverseValidationIssueOut(BaseModel):
    symbol: str = ""
    severity: Literal["info", "warning", "error"] = "warning"
    field: str = ""
    message: str = ""
    suggested_value: Any | None = None


class EtfUniverseValidationSummaryOut(BaseModel):
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    issues: list[EtfUniverseValidationIssueOut] = Field(default_factory=list)


class EtfUniverseDiffItemOut(BaseModel):
    symbol: str
    field: str
    baseline_value: Any = None
    current_value: Any = None
    draft_value: Any = None
    risk_level: Literal["low", "medium", "high"] = "low"
    message: str = ""


class EtfUniverseVersionSummaryOut(BaseModel):
    version: str = ""
    status: str = ""
    scope: str = ""
    description: str = ""
    created_by: str = ""
    created_at: str = ""
    activated_at: str = ""


class EtfUniverseAdminResponse(BaseModel):
    version: str = ""
    updated_at: str = ""
    audit_scope: str = "market.sector_etf_t0.universe_overrides"
    baseline_count: int = 0
    current_count: int = 0
    override_count: int = 0
    t0_enabled_count: int = 0
    items: list[EtfUniverseAdminProfileOut] = Field(default_factory=list)
    overrides: dict[str, dict[str, Any]] = Field(default_factory=dict)
    normalized_overrides: dict[str, dict[str, Any]] = Field(default_factory=dict)
    validation: EtfUniverseValidationSummaryOut = Field(default_factory=EtfUniverseValidationSummaryOut)
    diff: list[EtfUniverseDiffItemOut] = Field(default_factory=list)
    recent_versions: list[EtfUniverseVersionSummaryOut] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class EtfUniverseValidateRequest(BaseModel):
    draft_overrides: dict[str, dict[str, Any]] = Field(default_factory=dict)


class EtfUniverseRepairDraftRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=16)
    name: str = Field(default="", max_length=80)
    category: str = Field(default="", max_length=32)


class EtfUniverseApplyRequest(BaseModel):
    draft_overrides: dict[str, dict[str, Any]] = Field(default_factory=dict)
    version: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=500)
    activate: bool = False
    confirm_high_risk: bool = False


class EtfUniverseRollbackRequest(BaseModel):
    version: str = Field(min_length=1, max_length=80)
    confirm: bool = False


class EtfUniverseMutationResponse(BaseModel):
    ok: bool = True
    message: str = ""
    version: str = ""
    admin: EtfUniverseAdminResponse


class EtfMinuteSnapshotItem(BaseModel):
    symbol: str
    period: str = "1m"
    bar_count: int = 0
    latest_timestamp: str = ""
    latest_price: float = 0.0
    latest_amount: float = 0.0
    total_amount: float = 0.0
    high_price: float = 0.0
    low_price: float = 0.0
    age_seconds: float = 0.0
    data_quality: str = "unknown"
    bars: list[KlineBar] = Field(default_factory=list)
    strategy_decision: str = "none"
    note: str = ""


class EtfMinuteSnapshotBatchResponse(BaseModel):
    source: str = "go_market_read_service"
    period: str = "1m"
    data_quality: str = "unavailable"
    items: list[EtfMinuteSnapshotItem] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class SectorEtfT0Opportunity(BaseModel):
    sector_name: str
    etf_symbol: str
    etf_name: str
    etf_category: str = ""
    t0_eligible: bool = False
    settlement_rule: str = "t1"
    tracking_index: str = ""
    min_amount: float = 0.0
    max_spread_bps: float = 0.0
    slippage_bps: float = 0.0
    premium_discount_available: bool = False
    t0_eligibility_text: str = ""
    source_signal_symbol: str = ""
    source_signal_name: str = ""
    source_signal_state: str = ""
    source_strategy: str = ""
    source_signal_text: str = ""
    last_price: float = 0.0
    change_pct: float = 0.0
    bias: str = "hold"
    bias_text: str = "不做T"
    confidence: float = 0.0
    entry_zone: str = ""
    sell_zone: str = ""
    stop_loss: float = 0.0
    expected_edge_pct: float = 0.0
    intraday_signal_action: str = "unavailable"
    intraday_signal_text: str = "分钟信号待刷新"
    intraday_signal_confidence: float = 0.0
    intraday_signal_snapshot: dict[str, Any] = Field(default_factory=dict)
    intraday_risk_flags: list[str] = Field(default_factory=list)
    reason: str = ""
    risk: str = ""
    data_quality_text: str = ""


class SectorEtfT0Response(BaseModel):
    updated_at: str
    market_state: str = ""
    market_state_text: str = ""
    total: int = 0
    opportunities: list[SectorEtfT0Opportunity] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class IntradayAnomalyResponse(BaseModel):
    symbol: str
    name: str = ""
    updated_at: str
    anomaly_level: str = "normal"
    anomaly_text: str = "暂无异常"
    score: float = 0.0
    pattern: str = ""
    action_hint: str = ""
    reasons: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)
    data_quality_text: str = ""


class MarketModelValidationMetric(BaseModel):
    name: str
    status: str = "pending"
    sample_count: int = 0
    settled_count: int = 0
    pending_count: int = 0
    pass_rate_pct: float = 0.0
    avg_edge_pct: float = 0.0
    avg_return_1d_pct: float = 0.0
    avg_return_3d_pct: float = 0.0
    avg_max_adverse_5d_pct: float = 0.0
    false_positive_rate_pct: float = 0.0
    p_value: float = 1.0
    notes: str = ""


class MarketModelValidationResponse(BaseModel):
    model_key: str
    generated_at: str
    production_ready: bool = False
    acceptance_status: str = "pending"
    metrics: list[MarketModelValidationMetric] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class PairedHedgeLegOut(BaseModel):
    role: str
    symbol: str
    name: str = ""
    side: str = "long"
    notional_ratio: float = 0.0
    latest_price: float = 0.0
    change_pct: float = 0.0
    reason: str = ""


class PairedHedgeIdeaOut(BaseModel):
    source_signal_symbol: str
    source_signal_name: str = ""
    source_strategy: str = ""
    sector_name: str = ""
    confidence: float = 0.0
    hedge_ratio: float = 0.0
    gross_exposure_pct: float = 0.0
    net_exposure_pct: float = 0.0
    estimated_beta: float = 0.0
    hedge_cost_pct: float = 0.0
    tracking_error_pct: float = 0.0
    legs: list[PairedHedgeLegOut] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)


class PairedHedgeResearchResponse(BaseModel):
    updated_at: str
    mode: str = "research_only"
    disclaimer: str = "配对/对冲研究仅用于复盘和假设分析，不自动下单，不构成真实对冲或收益承诺。"
    total: int = 0
    ideas: list[PairedHedgeIdeaOut] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
