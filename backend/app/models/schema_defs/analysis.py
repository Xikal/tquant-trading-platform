from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from app.models.schema_defs.common import (
    ActionType,
    InstrumentOut,
    KlineBar,
    MarketEventOut,
    MicrostructureSnapshot,
    QuoteSnapshot,
    RiskLevel,
    SectorSnapshot,
    TradingRuleOut,
)


class AnalysisRequest(BaseModel):
    symbol: str = Field(..., description="证券代码")
    prefer_strategy: Literal["auto", "positive_t", "negative_t"] = "auto"
    base_position: int = 1000
    available_position: int = 1000
    cost_basis: Optional[float] = None
    include_ai: bool = True
    include_events: bool = True
    include_microstructure: bool = True


class StrategySuggestion(BaseModel):
    action: ActionType
    entry_price: Optional[float] = None
    exit_price: Optional[float] = None
    position_pct: float
    stop_loss: Optional[float] = None
    risk_level: RiskLevel
    signal_score: float
    tradability_score: float
    confidence: float
    expected_profit_pct: float = 0.0
    scenario: str
    trade_scene: str = ""
    trade_scene_text: str = ""
    signal_layer: Literal["hold", "watch_prepare", "light_execute", "strong_execute"] = "hold"
    signal_layer_text: str = "今天不做"
    near_action: ActionType = "hold"
    why_not_execute: str = ""
    buyback_trigger: str = ""
    reasons: list[str]
    blocking_rules: list[str]
    take_profit: Optional[float] = None
    strategy_notes: str = ""
    plain_action_text: str = ""
    plain_action_reason: str = ""
    plain_execution_text: str = ""
    plain_invalid_condition: str = ""
    estimated_fee: float = 0.0
    net_profit_pct: float = 0.0
    breakeven_pct: float = 0.0
    fee_warning: str = ""
    elasticity_score: float = 0.0
    elasticity_data_quality: str = "unavailable"
    elasticity_tier: str = ""
    liquidity_warning: str = ""
    suggested_timing: str = ""
    min_position_value: float = 0.0
    direction: str = ""
    min_shares_suggestion: int = 0
    effective_action: ActionType = "hold"
    is_actionable: bool = False


class AiInsight(BaseModel):
    enabled: bool
    summary: str
    confidence: float
    suggestions: list[str]
    warnings: list[str]
    raw: Optional[dict[str, Any]] = None


class AnalysisResponse(BaseModel):
    symbol: str
    instrument: InstrumentOut
    quote: QuoteSnapshot
    rules: TradingRuleOut
    sector: SectorSnapshot
    events: list[MarketEventOut]
    microstructure: MicrostructureSnapshot
    bars: list[KlineBar]
    metrics: dict[str, Any]
    suggestion: StrategySuggestion
    ai: AiInsight
    compliance_notes: list[str]
    assumptions: list[str]
    analysis_log_id: Optional[int] = None
