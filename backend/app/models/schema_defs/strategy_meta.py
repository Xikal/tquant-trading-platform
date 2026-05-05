from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class StrategyMetaOut(BaseModel):
    key: str
    name: str
    display_name: str
    description: str = ""
    category: str = ""
    risk_level: str = "medium"
    typical_holding_days: str = ""
    sort_order: int = 0


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
