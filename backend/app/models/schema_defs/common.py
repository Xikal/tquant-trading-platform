from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


ActionType = Literal["positive_t", "negative_t", "hold"]
RiskLevel = Literal["low", "medium", "high"]
InstrumentKind = Literal["all", "stock", "etf"]


class HealthResponse(BaseModel):
    status: str
    app: str


class ReadinessResponse(BaseModel):
    status: str
    app: str
    checks: dict[str, bool]
    errors: list[str] = Field(default_factory=list)


class InstrumentOut(BaseModel):
    symbol: str
    name: str
    market: str
    instrument_type: str
    sector_name: Optional[str] = None


class TradingRuleOut(BaseModel):
    symbol: str
    turnaround_mode: Literal["t0", "t1"]
    supports_positive_t: bool
    supports_negative_t: bool
    same_day_sell_allowed: bool
    requires_base_position: bool
    notes: str


class QuoteSnapshot(BaseModel):
    symbol: str
    name: str
    market: str
    instrument_type: str
    last_price: float
    change_pct: float
    change_amount: float
    open_price: float
    high_price: float
    low_price: float
    prev_close: float
    volume: float
    amount: float
    turnover_rate: Optional[float] = None
    volume_ratio: Optional[float] = None
    timestamp: str


class KlineBar(BaseModel):
    timestamp: str
    open: float
    close: float
    high: float
    low: float
    volume: float
    amount: float
    amplitude: Optional[float] = None
    change_pct: Optional[float] = None
    turnover: Optional[float] = None


class SectorSnapshot(BaseModel):
    sector_name: str
    sector_strength: float
    market_strength: float
    alignment_score: float
    notes: str


class MarketEventOut(BaseModel):
    title: str
    risk_level: RiskLevel
    description: str
    source: str
    event_time: str


class MicrostructureSnapshot(BaseModel):
    available: bool = False
    buy_pressure: float = 0.0
    sell_pressure: float = 0.0
    large_order_flow: float = 0.0
    notes: str = ""
