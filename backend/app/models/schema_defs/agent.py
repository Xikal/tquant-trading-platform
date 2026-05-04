from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


AgentToolPermission = Literal["read", "write", "notify", "dangerous"]


class AgentErrorOut(BaseModel):
    code: str
    message: str
    retryable: bool = False


class AgentHealthResponse(BaseModel):
    status: Literal["ok", "degraded"] = "ok"
    app: str
    agent_layer: str = "enabled"
    checks: dict[str, bool] = Field(default_factory=dict)
    updated_at: str
    errors: list[str] = Field(default_factory=list)


class AgentWatchlistContextItem(BaseModel):
    symbol: str
    name: str
    last_price: float = 0.0
    change_pct: float = 0.0
    action: str = "hold"
    action_text: str = "观望"
    signal_score: float = 0.0
    tradability_score: float = 0.0
    risk_level: str = "medium"
    base_position: int = 0
    available_position: int = 0
    cost_basis: Optional[float] = None
    summary: str = ""
    top_reasons: list[str] = Field(default_factory=list)
    blocking_rules: list[str] = Field(default_factory=list)


class AgentWatchlistContextResponse(BaseModel):
    updated_at: str
    total: int = 0
    actionable_count: int = 0
    high_risk_count: int = 0
    items: list[AgentWatchlistContextItem] = Field(default_factory=list)


class AgentPriorityBoardItem(BaseModel):
    rank: int
    symbol: str
    name: str
    sector_name: str = ""
    latest_price: float = 0.0
    change_pct: float = 0.0
    data_quality: str = "ok"
    data_quality_text: str = "数据完整"
    data_quality_tags: list[str] = Field(default_factory=list)
    market_state_category: str = "low_volume_wait"
    market_state_category_text: str = "缩量无主线"
    priority_score: float = 0.0
    buy_signal_text: str = ""
    strategy_titles: list[str] = Field(default_factory=list)
    entry_zone: str = ""
    stop_loss: float = 0.0
    suggested_position_text: str = ""
    summary: str = ""


class AgentPriorityBoardResponse(BaseModel):
    updated_at: str
    market_state_text: str = ""
    market_state_category: str = "low_volume_wait"
    market_state_category_text: str = "缩量无主线"
    data_quality: str = "ok"
    data_quality_text: str = "数据完整"
    data_quality_tags: list[str] = Field(default_factory=list)
    directional_bias: str = "neutral"
    directional_bias_text: str = "观望"
    total_candidates: int = 0
    immediate_count: int = 0
    focus_count: int = 0
    track_count: int = 0
    hot_industries: list[str] = Field(default_factory=list)
    items: list[AgentPriorityBoardItem] = Field(default_factory=list)


class AgentAnalysisRequest(BaseModel):
    symbol: str
    base_position: int = 1000
    available_position: int = 1000
    cost_basis: Optional[float] = None
    include_ai: bool = False


class AgentAnalysisResponse(BaseModel):
    symbol: str
    name: str
    last_price: float = 0.0
    change_pct: float = 0.0
    action: str = "hold"
    action_text: str = "观望"
    signal_score: float = 0.0
    tradability_score: float = 0.0
    risk_level: str = "medium"
    entry_price: Optional[float] = None
    exit_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    position_pct: float = 0.0
    expected_profit_pct: float = 0.0
    reasons: list[str] = Field(default_factory=list)
    blocking_rules: list[str] = Field(default_factory=list)
    summary: str = ""


class AgentPaperPositionItem(BaseModel):
    symbol: str
    name: str = ""
    quantity: int = 0
    available_quantity: int = 0
    cost_basis: float = 0.0
    latest_price: Optional[float] = None
    market_value: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0


class AgentPaperPortfolioResponse(BaseModel):
    updated_at: str
    account_id: Optional[int] = None
    total_assets: float = 0.0
    cash_available: float = 0.0
    market_value: float = 0.0
    total_return_pct: float = 0.0
    win_rate_pct: float = 0.0
    net_win_rate_pct: float = 0.0
    profit_factor: Optional[float] = None
    positions: list[AgentPaperPositionItem] = Field(default_factory=list)


class AgentOrderRecommendationRequest(BaseModel):
    limit: int = Field(default=12, ge=1, le=50)
    account_id: Optional[int] = None


class AgentOrderRecommendationItem(BaseModel):
    symbol: str
    name: str = ""
    side: str = "buy"
    quantity: int = 0
    price: float = 0.0
    strategy_key: str = ""
    reason: str = ""


class AgentOrderRecommendationResponse(BaseModel):
    updated_at: str
    account_id: Optional[int] = None
    will_buy: list[AgentOrderRecommendationItem] = Field(default_factory=list)
    filtered: list[dict[str, Any]] = Field(default_factory=list)
    summary: str = ""
    note: str = "仅生成模拟委托建议，不执行下单。"


class AgentBacktestRequest(BaseModel):
    strategy_key: str
    lookback_days: int = Field(default=60, ge=20, le=250)


class AgentBacktestResponse(BaseModel):
    strategy_key: str
    lookback_days: int
    evaluated_signals: int = 0
    filled_signals: int = 0
    win_rate: float = 0.0
    net_win_rate: float = 0.0
    avg_net_return_pct: float = 0.0
    profit_factor: float = 0.0
    max_adverse_pct: float = 0.0
    data_quality: str = "ok"
    data_quality_text: str = "数据完整"
    notes: list[str] = Field(default_factory=list)
    summary: str = ""


class AgentCompareStrategiesRequest(BaseModel):
    strategy_keys: list[str] = Field(min_length=1)
    lookback_days: int = Field(default=60, ge=20, le=250)


class AgentCompareStrategiesResponse(BaseModel):
    strategy_keys: list[str] = Field(default_factory=list)
    lookback_days: int
    strategy_count: int = 0
    items: list[dict[str, Any]] = Field(default_factory=list)
    best_strategy_key: str = ""
    summary: str = ""


class AgentPaperOrderRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=16)
    side: Literal["buy", "sell"]
    quantity: int = Field(ge=100, le=1_000_000)
    price: float = Field(gt=0)
    account_id: Optional[int] = None
    name: str = ""
    strategy_key: str = ""
    reason: str = "agent paper order"


class AgentPaperOrderResponse(BaseModel):
    ok: bool
    account_id: Optional[int] = None
    order_id: Optional[int] = None
    symbol: str
    side: str
    quantity: int
    price: float
    status: str = ""
    summary: str = ""


class AgentMarketSentimentResponse(BaseModel):
    updated_at: str
    state: str = ""
    state_text: str = ""
    breadth_ready: bool = False
    emotion_ready: bool = False
    stock_up_ratio: float = 0.0
    stock_median_change: float = 0.0
    limit_up_count: int = 0
    limit_down_count: Optional[int] = None
    broken_board_ratio: float = 0.0
    promotion_ratio: float = 0.0
    board_height: int = 0
    hot_industries: list[str] = Field(default_factory=list)
    hot_turnover: float = 0.0
    data_quality_text: str = ""


class AgentSectorHeatmapResponse(BaseModel):
    updated_at: str
    limit: int = 20
    sectors: list[dict[str, Any]] = Field(default_factory=list)
    data_quality_text: str = ""


class AgentPositionTSignalRequest(BaseModel):
    symbol: str
    shares: int = 0
    cost_basis: float = 0.0


class AgentPositionTSignalResponse(BaseModel):
    symbol: str
    name: str = ""
    action: str = "hold"
    action_text: str = "观望"
    signal_score: float = 0.0
    tradability_score: float = 0.0
    risk_level: str = "medium"
    entry_price: Optional[float] = None
    exit_price: Optional[float] = None
    stop_loss: Optional[float] = None
    position_pct: float = 0.0
    summary: str = ""
    reasons: list[str] = Field(default_factory=list)
    blocking_rules: list[str] = Field(default_factory=list)


class AgentCrossValidationRequest(BaseModel):
    symbols: list[str] = Field(default_factory=list, max_length=30)


class AgentRiskCheckRequest(BaseModel):
    proposals: list[dict[str, Any]] = Field(default_factory=list, max_length=50)


class AgentComprehensiveAnalysisRequest(BaseModel):
    symbols: list[str] = Field(default_factory=list, max_length=30)


class AgentAuditLogOut(BaseModel):
    trace_id: str
    agent_id: str = ""
    provider: str = ""
    tool_name: str
    outcome: str
    latency_ms: int = 0
    ip_address: str = ""
    params_snapshot: dict[str, Any] = Field(default_factory=dict)
    result_summary: str = ""
    created_at: Any = None


class AgentAuditToolStat(BaseModel):
    tool_name: str
    call_count: int = 0
    success_count: int = 0
    failure_count: int = 0


class AgentAuditSummaryResponse(BaseModel):
    db_available: bool = True
    recent_limit: int = 100
    recent_call_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    tool_top: list[AgentAuditToolStat] = Field(default_factory=list)


class AgentDailyReportResponse(BaseModel):
    trade_date: str
    generated_at: str
    headline: str
    watchlist_summary: dict[str, Any] = Field(default_factory=dict)
    priority_board_summary: dict[str, Any] = Field(default_factory=dict)
    top_opportunities: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    market_overview: dict[str, Any] = Field(default_factory=dict)
    sector_mainline: dict[str, Any] = Field(default_factory=dict)
    holding_t_signals: list[dict[str, Any]] = Field(default_factory=list)
    stock_top: list[dict[str, Any]] = Field(default_factory=list)
    risk_check: dict[str, Any] = Field(default_factory=dict)
    operation_checklist: list[str] = Field(default_factory=list)
    markdown: str = ""


class AgentDailyReportPushRequest(BaseModel):
    channel: str = "feishu"


class AgentDailyReportPushResponse(BaseModel):
    ok: bool
    channel: str = "feishu"
    trade_date: str
    generated_at: str = ""
    sent: bool = False
    should_notify: bool = False
    duplicate: bool = False
    notification_count: int = 0
    message: str = ""
    markdown: str = ""


class AgentResearchWorkflowRunRequest(BaseModel):
    channel: str = "feishu"
    open_id: str = ""
    symbols: list[str] = Field(default_factory=list, max_length=10)


class AgentResearchWorkflowStatusResponse(BaseModel):
    job_id: str = ""
    workflow_name: str = "tquant_daily_research"
    status: str = "not_found"
    message: str = ""
    symbols: list[str] = Field(default_factory=list)
    markdown: str = ""
    notification_sent: bool = False


class AgentNotificationTestRequest(BaseModel):
    channel: str = "feishu"
    message: str = "测试消息"


class AgentNotificationTestResponse(BaseModel):
    ok: bool
    channel: str
    message: str


class AgentSignalNotificationRequest(BaseModel):
    channel: str = "feishu"
    symbol: str
    name: str = ""
    strategy_key: str = ""
    strategy_title: str = ""
    signal_state: str = ""
    signal_text: str = ""
    message: str = ""
    event_type: str = "signal"
    payload: dict[str, Any] = Field(default_factory=dict)


class AgentSignalNotificationScanRequest(BaseModel):
    limit: int = Field(default=12, ge=1, le=50)
    channel: str = "feishu"


class AgentSignalNotificationResponse(BaseModel):
    ok: bool
    channel: str
    symbol: str
    strategy_key: str = ""
    signal_state: str = ""
    should_notify: bool = False
    upgraded: bool = False
    notification_count: int = 0
    message: str = ""


class AgentSignalNotificationScanResponse(BaseModel):
    ok: bool = True
    channel: str = "feishu"
    scanned: int = 0
    sent: int = 0
    suppressed: int = 0
    upgraded: int = 0
    errors: list[str] = Field(default_factory=list)
    message: str = ""


class AgentProviderHealth(BaseModel):
    provider: str
    available: bool
    external_agent: bool = False
    warnings: list[str] = Field(default_factory=list)


class AgentProviderStatusResponse(BaseModel):
    provider: str
    available: bool
    external_agent: bool = False
    write_tools_enabled: bool = False
    notify_tools_enabled: bool = False
    audit_enabled: bool = True
    tool_count: int = 0
    enabled_tools: list[str] = Field(default_factory=list)
    disabled_tools: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class AgentToolInvokeRequest(BaseModel):
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class AgentToolResult(BaseModel):
    ok: bool
    provider: str
    tool_name: str
    data: Optional[Any] = None
    error: Optional[AgentErrorOut] = None
    duration_ms: int = 0
    trace_id: str
