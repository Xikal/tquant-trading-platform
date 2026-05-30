from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class StrategyMetaOut(BaseModel):
    key: str
    name: str
    display_name: str
    description: str = ""
    tier: str = "research"
    category_key: str = "research"
    category: str = ""
    display_category: str = ""
    risk_level: str = "medium"
    typical_holding_days: str = ""
    sort_order: int = 0
    enabled: bool = True
    probe_status: str = "not_required"
    probe_summary: str = ""
    visibility: str = "full"
    promotion_eligible: bool = False
    promotion_status_text: str = ""
    promotion_filled_signals: int = 0
    promotion_health_score: float = 0.0
    promotion_required_filled: int = 0
    promotion_required_health: float = 0.0


class StrategyMetaResponse(BaseModel):
    strategies: list[StrategyMetaOut] = Field(default_factory=list)


class StrategyPresetOut(BaseModel):
    id: int | None = None
    key: str = ""
    name: str
    description: str = ""
    config: dict[str, Any] = Field(default_factory=dict)
    sort_order: int = 0


class StrategyPresetResponse(BaseModel):
    presets: list[StrategyPresetOut] = Field(default_factory=list)


class StrategyGovernanceMutationRequest(BaseModel):
    strategy_key: str = Field(..., min_length=1, max_length=80)
    target_tier: str = Field(default="auxiliary", max_length=20)
    reason: str = Field(default="", max_length=500)
    evidence_summary: str = Field(default="", max_length=1000)


class StrategyGovernanceMutationResponse(BaseModel):
    ok: bool = True
    strategy_key: str
    action: str
    tier: str = ""
    message: str = ""


class SymbolSearchItem(BaseModel):
    symbol: str
    name: str = ""
    latest_price: float | None = None
    industry: str = ""
    market: str = ""
    instrument_type: str = "stock"


class SymbolSearchResponse(BaseModel):
    items: list[SymbolSearchItem] = Field(default_factory=list)
    total: int = 0


class StrategySignalReplayItem(BaseModel):
    latest_trade_date: str
    strategy_key: str
    symbol: str
    name: str = ""
    buy_signal_state: str = ""
    buy_signal_text: str = ""
    score: float = 0.0
    latest_price: float | None = None
    change_pct: float | None = None
    entry_zone: str = ""
    stop_loss: float | None = None
    suggested_position_text: str = ""
    summary: str = ""
    reasons: list[str] = Field(default_factory=list)
    updated_at: str = ""


class StrategySignalReplayResponse(BaseModel):
    items: list[StrategySignalReplayItem] = Field(default_factory=list)
    total: int = 0


class StrategyPromotionReviewOut(BaseModel):
    strategy_key: str
    current_tier: str = "research"
    recommended_tier: str = "research"
    recommendation: str = "stay_research"
    evidence: dict[str, Any] = Field(default_factory=dict)
    blocking_reasons: list[str] = Field(default_factory=list)
    can_apply_override: bool = False
