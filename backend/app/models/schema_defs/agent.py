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
    latest_price: float = 0.0
    change_pct: float = 0.0
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


class AgentDailyReportResponse(BaseModel):
    trade_date: str
    generated_at: str
    headline: str
    watchlist_summary: dict[str, Any] = Field(default_factory=dict)
    priority_board_summary: dict[str, Any] = Field(default_factory=dict)
    top_opportunities: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)


class AgentNotificationTestRequest(BaseModel):
    channel: str = "feishu"
    message: str = "测试消息"


class AgentNotificationTestResponse(BaseModel):
    ok: bool
    channel: str
    message: str


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
