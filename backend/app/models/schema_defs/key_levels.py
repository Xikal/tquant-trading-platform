from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

KeyLevelDirection = Literal["support", "resistance", "neutral"]
KeyLevelScope = Literal["stock", "sector", "market"]
KeyLevelType = Literal[
    "volume_profile",
    "swing_high",
    "swing_low",
    "platform_high",
    "platform_low",
    "gap",
    "limit_up_anchor",
    "anchored_vwap",
    "ma5",
    "ma10",
    "ma20",
    "ma30",
    "ma60",
    "intraday_vwap",
    "open",
    "prev_close",
    "round_number",
]
KeyLevelDataQuality = Literal["ok", "insufficient", "stale", "blocked", "research_only"]


class KeyLevelCandidate(BaseModel):
    price: float
    zone_low: float
    zone_high: float
    direction: KeyLevelDirection
    level_type: KeyLevelType
    strength_score: int = Field(ge=0, le=100)
    evidence: list[str] = Field(default_factory=list)
    invalid_condition: str = ""
    last_touched_date: str | None = None
    touch_count: int | None = None
    source_window_days: int | None = None
    invalidate_below: float | None = None
    invalidate_volume_x: float | None = None


class KeyLevelResult(BaseModel):
    symbol: str
    name: str = ""
    scope: KeyLevelScope
    trade_date: str
    latest_price: float
    engine_version: str = "akey-level-v1"
    as_of: str
    adjust_mode: Literal["qfq", "hfq", "none"] = "qfq"
    intraday_included: bool = False
    support_price: float | None = None
    support_zone_low: float | None = None
    support_zone_high: float | None = None
    support_distance_pct: float | None = None
    support_strength: int = Field(default=0, ge=0, le=100)
    support_level_type: KeyLevelType | Literal[""] = ""
    resistance_price: float | None = None
    resistance_zone_low: float | None = None
    resistance_zone_high: float | None = None
    resistance_distance_pct: float | None = None
    resistance_strength: int = Field(default=0, ge=0, le=100)
    resistance_level_type: KeyLevelType | Literal[""] = ""
    ma5: float | None = None
    ma10: float | None = None
    ma20: float | None = None
    ma30: float | None = None
    ma60: float | None = None
    close_to_ma5: float | None = None
    close_to_ma10: float | None = None
    close_to_ma20: float | None = None
    close_to_ma30: float | None = None
    close_to_ma60: float | None = None
    trend_above_ma30: bool | None = None
    trend_above_ma60: bool | None = None
    key_level_candidates: list[KeyLevelCandidate] = Field(default_factory=list)
    data_quality: KeyLevelDataQuality = "insufficient"
    explanation: str = "数据不足，仅观察。"
    warnings: list[str] = Field(default_factory=list)
