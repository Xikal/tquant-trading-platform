from __future__ import annotations

from typing import Any, Literal, Optional

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

