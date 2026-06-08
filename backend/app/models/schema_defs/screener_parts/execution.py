from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from app.models.schema_defs.screener_parts.common import BuySignalState

class LowBuyExecutionBacktestItemOut(BaseModel):
    symbol: str
    name: str
    strategy_key: str
    signal_trade_date: str
    entry_trade_date: Optional[str] = None
    exit_trade_date: Optional[str] = None
    status: Literal["filled", "not_filled", "invalid"] = "not_filled"
    entry_price: float = 0.0
    exit_price: float = 0.0
    net_return_pct: float = 0.0
    max_gain_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    exit_reason: str = ""
    data_quality: str = "ok"
    data_quality_text: str = "数据完整"
    data_quality_tags: list[str] = Field(default_factory=list)

class LowBuyExecutionBacktestResponse(BaseModel):
    strategy_key: str
    lookback_days: int
    evaluated_signals: int = 0
    filled_signals: int = 0
    not_filled_signals: int = 0
    invalid_signals: int = 0
    win_rate: float = 0.0
    net_win_rate: float = 0.0
    not_filled_rate: float = 0.0
    stop_loss_count: int = 0
    stop_loss_rate: float = 0.0
    take_profit_count: int = 0
    take_profit_rate: float = 0.0
    time_exit_count: int = 0
    time_exit_rate: float = 0.0
    avg_net_return_pct: float = 0.0
    avg_max_gain_pct: float = 0.0
    avg_max_drawdown_pct: float = 0.0
    max_adverse_pct: float = 0.0
    avg_loss_pct: float = 0.0
    win_loss_ratio: float = 0.0
    profit_factor: float = 0.0
    data_quality: str = "ok"
    data_quality_text: str = "数据完整"
    data_quality_tags: list[str] = Field(default_factory=list)
    pbo: Optional[dict[str, Any]] = None
    crisis_scenario: Optional[dict[str, Any]] = None
    notes: list[str] = Field(default_factory=list)
    items: list[LowBuyExecutionBacktestItemOut] = Field(default_factory=list)

class LowBuyTradeLifecycleOut(BaseModel):
    symbol: str
    name: str = ""
    strategy_key: str
    signal_trade_date: str
    status: Literal["planned", "entered", "holding", "exited", "invalid"] = "planned"
    signal_state: BuySignalState = "watch"
    entry_plan_low: float = 0.0
    entry_plan_high: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    max_holding_days: int = 5
    entry_price: Optional[float] = None
    entry_trade_date: Optional[str] = None
    exit_price: Optional[float] = None
    exit_trade_date: Optional[str] = None
    exit_reason: str = ""
    realized_return_pct: float = 0.0
    max_gain_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    attribution_note: str = ""
    updated_at: str = ""

class LowBuyTradeLifecycleUpdate(BaseModel):
    signal_trade_date: str = Field(..., min_length=1)
    strategy_key: str = "first_board"
    status: Optional[Literal["planned", "entered", "holding", "exited", "invalid"]] = None
    entry_price: Optional[float] = None
    entry_trade_date: Optional[str] = None
    exit_price: Optional[float] = None
    exit_trade_date: Optional[str] = None
    exit_reason: Optional[str] = None
    realized_return_pct: Optional[float] = None
    max_gain_pct: Optional[float] = None
    max_drawdown_pct: Optional[float] = None
    attribution_note: Optional[str] = None


LowBuyTradeLifecycleOut.model_rebuild(_types_namespace={"BuySignalState": BuySignalState})
