from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from app.models.schema_defs.common import ActionType


class ReplayOut(BaseModel):
    id: int
    symbol: str
    outcome: str
    pnl_pct: float
    max_favorable_excursion: float
    max_adverse_excursion: float
    review_notes: str
    created_at: datetime


class BacktestRequest(BaseModel):
    symbol: str
    lookback_bars: int = 360
    bar_period: Literal["1m", "5m", "15m"] = "5m"
    initial_position: int = 1000
    walk_forward_windows: int = 3


class BacktestTrade(BaseModel):
    timestamp: str
    action: ActionType
    entry_price: float
    exit_price: float
    pnl_pct: float
    signal_score: float


class BacktestResponse(BaseModel):
    run_id: Optional[int] = None
    symbol: str
    total_trades: int
    win_rate: float
    avg_pnl_pct: float
    profit_factor: float
    max_drawdown: float
    walk_forward_score: float
    trades: list[BacktestTrade]


class BacktestRunOut(BaseModel):
    id: int
    name: str = ""
    params: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class BacktestRunListResponse(BaseModel):
    runs: list[BacktestRunOut] = Field(default_factory=list)


class StrategyValidationRequest(BaseModel):
    strategies: list[str] = Field(default_factory=lambda: ["first_board", "volume_shrink"])
    lookback_days: int = Field(default=120, ge=20, le=520)
    initial_cash: float = Field(default=100000.0, gt=0)
    max_signals_per_day: int = Field(default=8, ge=1, le=50)


class StrategyValidationItem(BaseModel):
    strategy_key: str
    evaluated_signals: int = 0
    filled_signals: int = 0
    win_rate_pct: float = 0.0
    net_win_rate_pct: float = 0.0
    avg_return_pct: float = 0.0
    profit_factor: Optional[float] = None
    max_drawdown_pct: float = 0.0
    pbo_risk: str = "insufficient_sample"
    by_market_state: dict[str, Any] = Field(default_factory=dict)


class StrategyValidationReport(BaseModel):
    run_id: Optional[int] = None
    generated_at: datetime
    lookback_days: int
    strategy_count: int
    total_filled_signals: int
    items: list[StrategyValidationItem]
    summary: str


class StrategyComparisonRequest(BaseModel):
    baseline_strategy: str = "first_board"
    candidate_strategies: list[str] = Field(default_factory=lambda: ["volume_shrink"])
    lookback_days: int = Field(default=120, ge=20, le=520)


class IntradayConfirmationOut(BaseModel):
    symbol: str
    name: str = ""
    trade_date: str
    vwap: float = 0.0
    latest_price: float = 0.0
    above_vwap: bool = False
    confirmed: bool = False
    late_confirmed: bool = False
    score: float = 0.0
    reason: str = ""
    profile: dict[str, Any] = Field(default_factory=dict)
    big_order: dict[str, Any] = Field(default_factory=dict)
    tick: dict[str, Any] = Field(default_factory=dict)
    updated_at: Optional[datetime] = None


class IntradayConfirmationRequest(BaseModel):
    symbols: list[str] = Field(default_factory=list)
    period: Literal["1m", "5m"] = "1m"
    limit: int = Field(default=120, ge=20, le=240)


class RiskEventOut(BaseModel):
    id: int
    account_id: Optional[int] = None
    symbol: str = ""
    event_type: str
    severity: str
    status: str
    message: str
    triggered_at: datetime
