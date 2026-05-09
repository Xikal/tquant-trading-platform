from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from app.models.schema_defs.screener_parts.common import BuySignalState

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

