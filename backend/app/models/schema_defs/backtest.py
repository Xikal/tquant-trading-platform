from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


BacktestStatus = Literal["queued", "running", "succeeded", "failed", "cancelled", "deleted"]


class BacktestRunCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    name: str = Field(default="", max_length=80)
    strategy_keys: list[str] = Field(default_factory=list, alias="strategies")
    start_date: str = Field(..., min_length=8, max_length=16)
    end_date: str = Field(..., min_length=8, max_length=16)
    initial_cash: float = Field(default=100000.0, gt=0, alias="initial_capital")
    benchmark_symbol: str = Field(default="000300", max_length=24, alias="benchmark")
    dataset_manifest_id: Optional[int] = None
    engine_version: str = Field(default="backtest-v2", max_length=48)
    strategy_version: str = Field(default="", max_length=80)
    data_version: str = Field(default="", max_length=80)
    fee_model_version: str = Field(default="", max_length=80)
    slippage_bps: float = Field(default=8.0, ge=0, le=200)
    params: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def collect_documented_extra_params(self) -> "BacktestRunCreate":
        extra = getattr(self, "__pydantic_extra__", None) or {}
        params = dict(self.params)
        for key in ("execution_model", "risk_limits", "param_overrides", "slippage_model"):
            if key in extra and key not in params:
                params[key] = extra[key]
        self.params = params
        return self


class BacktestRunSummary(BaseModel):
    id: int
    name: str
    status: str
    strategy_keys: list[str] = Field(default_factory=list)
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    initial_cash: float = 0.0
    final_equity: float = 0.0
    progress_pct: float = 0.0
    benchmark_symbol: str = ""
    owner_user_id: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None


class BacktestRunDetail(BacktestRunSummary):
    params: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    dataset_manifest_id: Optional[int] = None
    engine_version: str = ""
    strategy_version: str = ""
    data_version: str = ""
    fee_model_version: str = ""
    slippage_bps: float = 0.0
    error_message: str = ""


class BacktestRunListResponse(BaseModel):
    items: list[BacktestRunSummary] = Field(default_factory=list)
    total: int = 0
    limit: int
    offset: int


class BacktestEquityPoint(BaseModel):
    trade_date: str
    cash: float = 0.0
    market_value: float = 0.0
    equity: float = 0.0
    daily_return_pct: float = 0.0
    drawdown_pct: float = 0.0
    exposure_pct: float = 0.0
    positions_count: int = 0
    turnover: float = 0.0
    benchmark_symbol: str = ""
    benchmark_close: float = 0.0
    benchmark_return_pct: float = 0.0
    payload: dict[str, Any] = Field(default_factory=dict)


class BacktestEquityResponse(BaseModel):
    run_id: int
    items: list[BacktestEquityPoint] = Field(default_factory=list)


class BacktestTradeOut(BaseModel):
    id: int
    run_id: int
    order_id: Optional[int] = None
    trade_date: str
    symbol: str
    name: str = ""
    side: str
    strategy_key: str = ""
    signal_state: str = ""
    quantity: int = 0
    price: float = 0.0
    gross_amount: float = 0.0
    fee_amount: float = 0.0
    slippage_amount: float = 0.0
    net_amount: float = 0.0
    pnl_amount: float = 0.0
    pnl_pct: float = 0.0
    holding_days: int = 0
    entry_reason: str = ""
    exit_reason: str = ""
    market_state: str = ""
    sector_name: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class BacktestTradesResponse(BaseModel):
    run_id: int
    items: list[BacktestTradeOut] = Field(default_factory=list)
    total: int = 0
    limit: int
    offset: int


class BacktestMutationResponse(BaseModel):
    ok: bool = True
    run_id: int
    status: str
    message: str = ""
