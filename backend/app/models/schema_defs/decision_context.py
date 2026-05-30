from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field


GateDecision = Literal["allow", "reduce", "block", "wait", "research_only", "no_data"]
StrategyTierName = Literal["core", "aux", "auxiliary", "research", "factor"]
FinalDecision = Literal["front_row", "candidate", "watch", "research_only", "blocked"]
DataQuality = Literal["ok", "degraded", "missing", "blocked"]


class GateDecisionOut(BaseModel):
    decision: GateDecision
    score: float = Field(ge=0.0, le=100.0)
    reasons: list[str] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)


class DecisionContextOut(BaseModel):
    symbol: str
    trade_date: date
    strategy_key: str
    strategy_tier: StrategyTierName
    production_eligible: bool
    market_gate: GateDecisionOut
    sector_leader_gate: GateDecisionOut
    hard_risk_gate: GateDecisionOut
    event_risk_gate: GateDecisionOut
    intraday_entry_gate: GateDecisionOut
    final_decision: FinalDecision
    final_score: float
    data_quality: DataQuality


class IntradayEntryDecisionRequest(BaseModel):
    symbol: str
    strategy_key: str = "unknown"
    trade_date: date
    entry_zone_low: float | None = None
    entry_zone_high: float | None = None
    support_price: float | None = None
    latest_price: float | None = None


class IntradayEntryDecisionOut(BaseModel):
    symbol: str
    strategy_key: str
    trade_date: date
    intraday_entry_decision: Literal["buy_now", "wait", "avoid", "no_data"]
    data_quality: DataQuality | Literal["no_data", "missing"]
    reasons: list[str] = Field(default_factory=list)
    entry_zone_low: float | None = None
    entry_zone_high: float | None = None
    vwap_distance_pct: float | None = None
    support_distance_pct: float | None = None
    confirmation_text: str = ""
    production_score_delta: float = 0.0
