from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

PaperSide = Literal["buy", "sell"]
PaperOrderType = Literal["market", "limit"]
PaperOrderStatus = Literal["pending", "filled", "partial", "rejected", "cancelled"]


class PaperAccountCreate(BaseModel):
    name: str = Field(default="默认模拟账户", max_length=100)
    initial_cash: float = Field(default=100000.0, gt=0)


class PaperAccountOut(BaseModel):
    id: int
    user_id: Optional[int] = None
    name: str
    initial_cash: float
    cash_available: float
    frozen_cash: float = 0.0
    market_value: float = 0.0
    total_assets: float
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    total_return_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    status: str = "active"
    today_return_pct: float = 0.0


class PaperPositionOut(BaseModel):
    id: int
    symbol: str
    name: str = ""
    quantity: int
    available_quantity: int
    frozen_quantity: int = 0
    cost_basis: float
    latest_price: Optional[float] = None
    market_value: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    strategy_sources: list[str] = Field(default_factory=list)
    opened_at: datetime
    smart_exit_action: str = "hold"
    smart_exit_text: str = "继续观察"
    smart_exit_reason: str = ""
    smart_exit_invalid_condition: str = ""
    smart_exit_failure_action: str = ""
    smart_exit_quantity: int = 0
    smart_exit_net_profit_pct: float = 0.0
    smart_exit_fee_drag_pct: float = 0.0


class PaperPositionsResponse(BaseModel):
    positions: list[PaperPositionOut] = Field(default_factory=list)
    total_market_value: float = 0.0
    total_unrealized_pnl: float = 0.0


class PaperOrderCreate(BaseModel):
    symbol: str = Field(min_length=1, max_length=16)
    name: str = Field(default="", max_length=64)
    side: PaperSide
    order_type: PaperOrderType = "market"
    quantity: int = Field(gt=0)
    price: Optional[float] = Field(default=None, gt=0)
    strategy_key: str = Field(default="", max_length=80)
    reason: str = Field(default="", max_length=500)
    source: str = Field(default="manual", max_length=20)
    signal_snapshot: dict[str, Any] = Field(default_factory=dict)
    require_intraday_confirmation: bool = False
    current_price: Optional[float] = Field(default=None, gt=0)
    quote_time: Optional[datetime] = None
    is_suspended: bool = False
    up_limit: Optional[float] = None
    down_limit: Optional[float] = None


class PaperOrderOut(BaseModel):
    id: int
    account_id: int
    symbol: str
    name: str = ""
    side: PaperSide
    order_type: PaperOrderType
    price: Optional[float] = None
    quantity: int
    filled_quantity: int = 0
    avg_fill_price: Optional[float] = None
    status: PaperOrderStatus
    reject_reason: Optional[str] = None
    source: str = "manual"
    strategy_key: str = ""
    reason: str = ""
    created_at: datetime


class PaperTradeOut(BaseModel):
    id: int
    order_id: int
    account_id: int
    symbol: str
    side: PaperSide
    price: float
    quantity: int
    gross_amount: float
    commission: float
    stamp_tax: float
    transfer_fee: float
    net_amount: float
    strategy_key: str = ""
    entry_reason: str = ""
    entry_reason_code: str = ""
    exit_reason: str = ""
    exit_reason_code: str = ""
    commission_warning: str = ""
    trade_time: datetime


class PaperTradesResponse(BaseModel):
    trades: list[PaperTradeOut] = Field(default_factory=list)


class PaperTradeTagCreate(BaseModel):
    tag: str = Field(min_length=1, max_length=40)
    note: str = Field(default="", max_length=240)


class PaperTradeTagOut(BaseModel):
    id: int
    trade_id: int
    tag: str
    note: str = ""
    created_at: datetime


class PaperTagPerformanceOut(BaseModel):
    tag: str
    trades: int = 0
    win_rate_pct: float = 0.0
    net_win_rate_pct: float = 0.0
    avg_return_pct: float = 0.0
    total_return_pct: float = 0.0


class PaperPerformanceOut(BaseModel):
    total_return_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    win_rate_pct: float = 0.0
    net_win_rate_pct: float = 0.0
    avg_trade_return_pct: float = 0.0
    avg_win_pct: float = 0.0
    avg_loss_pct: float = 0.0
    profit_factor: Optional[float] = None
    sharpe_ratio: float = 0.0
    stop_loss_rate_pct: float = 0.0
    total_trades: int = 0
    avg_hold_days: float = 0.0
    win_loss_ratio: Optional[float] = None


class PaperGroupedPerformanceOut(BaseModel):
    key: str
    trades: int = 0
    win_rate_pct: float = 0.0
    net_win_rate_pct: float = 0.0
    avg_return_pct: float = 0.0
    profit_factor: Optional[float] = None


class PaperStrategyMarketPerformanceOut(BaseModel):
    strategy_key: str
    market_state: str
    trades: int = 0
    win_rate_pct: float = 0.0
    net_win_rate_pct: float = 0.0
    avg_return_pct: float = 0.0
    profit_factor: Optional[float] = None


class PaperStrategyCorrelationRowOut(BaseModel):
    strategy_key: str
    correlations: dict[str, Optional[float]] = Field(default_factory=dict)


class PaperStrategyCorrelationResponse(BaseModel):
    strategies: list[str] = Field(default_factory=list)
    sample_days: int = 0
    matrix: list[list[Optional[float]]] = Field(default_factory=list)
    rows: list[PaperStrategyCorrelationRowOut] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class PaperSectorEtfT0PerformanceOut(BaseModel):
    simulated_trades: int = 0
    simulated_closed_trades: int = 0
    simulated_win_rate_pct: float = 0.0
    simulated_net_win_rate_pct: float = 0.0
    simulated_avg_return_pct: float = 0.0
    simulated_profit_factor: Optional[float] = None
    shadow_sample_count: int = 0
    shadow_settled_count: int = 0
    shadow_pending_count: int = 0
    shadow_success_rate_pct: float = 0.0
    shadow_avg_return_1d_pct: float = 0.0
    shadow_avg_return_3d_pct: float = 0.0
    notes: list[str] = Field(default_factory=list)


class PaperRiskStatusOut(BaseModel):
    account_status: str = "active"
    total_assets: float = 0.0
    max_single_order_pct: float = 30.0
    max_single_symbol_position_pct: float = 40.0
    max_daily_buy_pct: float = 60.0
    max_daily_order_count: int = 20
    daily_order_count: int = 0
    daily_buy_used_pct: float = 0.0


class PaperAgentRunOut(BaseModel):
    id: int
    account_id: int
    provider: str = ""
    run_type: str = ""
    status: str = ""
    request: dict[str, Any] = Field(default_factory=dict)
    response: dict[str, Any] = Field(default_factory=dict)
    error_message: str = ""
    created_at: datetime
