from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

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

