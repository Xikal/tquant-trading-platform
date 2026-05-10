from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


BacktestStatus = Literal["queued", "running", "succeeded", "failed", "cancelled", "timeout", "deleted"]
BacktestResearchStatus = Literal["queued", "running", "succeeded", "failed", "cancelled", "deleted"]
OptimizationTarget = Literal["sharpe", "total_return_pct", "profit_factor", "win_rate_pct"]
ALLOWED_OPTIMIZATION_PARAMS = {
    "min_score",
    "max_position_pct",
    "max_holding_days",
    "stop_loss_pct",
    "take_profit_pct",
}


def default_walk_forward_param_grid() -> dict[str, list[Any]]:
    return {
        "min_score": [70, 80, 85],
        "max_holding_days": [3, 5],
    }


class BacktestAttributionBucket(BaseModel):
    bucket: str
    label: str = ""
    signal_count: int = 0
    filled_order_count: int = 0
    rejected_order_count: int = 0
    trade_count: int = 0
    win_count: int = 0
    win_rate_pct: float = 0.0
    avg_return_pct: float = 0.0
    net_pnl: float = 0.0
    fee_amount: float = 0.0


class BacktestAttribution(BaseModel):
    version: str = ""
    industry: list[BacktestAttributionBucket] = Field(default_factory=list)
    market_state: list[BacktestAttributionBucket] = Field(default_factory=list)
    data_quality: list[BacktestAttributionBucket] = Field(default_factory=list)
    data_quality_summary: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


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
    max_duration_seconds: int = Field(default=1800, ge=1, le=86400)
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
    summary: dict[str, Any] = Field(default_factory=dict)
    queue_depth: int = 0
    queue_position: Optional[int] = None
    running_count: int = 0
    estimated_wait_seconds: int = 0
    created_at: datetime
    updated_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None


class BacktestRunDetail(BacktestRunSummary):
    params: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    result_quality: dict[str, Any] = Field(default_factory=dict)
    attribution: BacktestAttribution = Field(default_factory=BacktestAttribution)
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
    benchmark_nav: float = 1.0
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


class BacktestMonthlyReturn(BaseModel):
    month: str
    start_equity: float = 0.0
    end_equity: float = 0.0
    return_pct: float = 0.0
    trading_days: int = 0


class BacktestMonthlyReturnsResponse(BaseModel):
    run_id: int
    items: list[BacktestMonthlyReturn] = Field(default_factory=list)


class BacktestCompareRequest(BaseModel):
    run_ids: list[int] = Field(..., min_length=1, max_length=10)


class BacktestCompareItem(BaseModel):
    run_id: int
    name: str = ""
    status: str = ""
    strategy_keys: list[str] = Field(default_factory=list)
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    initial_cash: float = 0.0
    final_equity: float = 0.0
    metrics: dict[str, Any] = Field(default_factory=dict)


class BacktestCompareEquityPoint(BaseModel):
    trade_date: str
    equity: float = 0.0
    daily_return_pct: float = 0.0
    drawdown_pct: float = 0.0


class BacktestCompareEquityCurve(BaseModel):
    run_id: int
    points: list[BacktestCompareEquityPoint] = Field(default_factory=list)


class BacktestCompareResponse(BaseModel):
    run_ids: list[int] = Field(default_factory=list)
    items: list[BacktestCompareItem] = Field(default_factory=list)
    equity_curves: list[BacktestCompareEquityCurve] = Field(default_factory=list)


class BacktestStrategyAttributionItem(BaseModel):
    strategy_key: str
    trade_count: int = 0
    net_pnl: float = 0.0
    win_rate_pct: float = 0.0
    avg_return_pct: float = 0.0


class BacktestAttributionResponse(BaseModel):
    run_id: int
    strategy: list[BacktestStrategyAttributionItem] = Field(default_factory=list)
    industry: list[dict[str, Any]] = Field(default_factory=list)
    market_state: list[dict[str, Any]] = Field(default_factory=list)
    data_quality: list[dict[str, Any]] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class BacktestCorrelationRow(BaseModel):
    strategy_key: str
    correlations: dict[str, float] = Field(default_factory=dict)
    p_values: dict[str, float] = Field(default_factory=dict)
    sample_counts: dict[str, int] = Field(default_factory=dict)
    significance_notes: dict[str, str] = Field(default_factory=dict)


class BacktestStrategyCorrelationResponse(BaseModel):
    run_id: int
    strategies: list[str] = Field(default_factory=list)
    matrix: list[BacktestCorrelationRow] = Field(default_factory=list)


class BacktestMutationResponse(BaseModel):
    ok: bool = True
    run_id: int
    status: str
    message: str = ""


class BacktestOptimizationCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    name: str = Field(default="", max_length=120)
    strategy: str = Field(..., min_length=1, max_length=80, alias="strategy_key")
    param_grid: dict[str, list[Any]]
    train_start: str = Field(..., min_length=8, max_length=16)
    train_end: str = Field(..., min_length=8, max_length=16)
    test_start: str = Field(..., min_length=8, max_length=16)
    test_end: str = Field(..., min_length=8, max_length=16)
    optimization_target: OptimizationTarget = "sharpe"
    initial_cash: float = Field(default=100000.0, gt=0, alias="initial_capital")
    benchmark_symbol: str = Field(default="000300", max_length=24, alias="benchmark")
    execution_model: str = Field(default="conservative_slippage", max_length=40)
    max_combinations: int = Field(default=500, ge=1, le=500)

    @model_validator(mode="after")
    def validate_param_grid(self) -> "BacktestOptimizationCreate":
        invalid = sorted(set(self.param_grid) - ALLOWED_OPTIMIZATION_PARAMS)
        if invalid:
            raise ValueError(f"不支持优化参数: {', '.join(invalid)}")
        cleaned: dict[str, list[Any]] = {}
        for key, values in self.param_grid.items():
            if not isinstance(values, list) or not values:
                raise ValueError(f"{key} 必须提供非空取值列表")
            cleaned[key] = values
        self.param_grid = cleaned
        if self.train_start > self.train_end or self.test_start > self.test_end:
            raise ValueError("训练期或测试期日期范围无效")
        if self.train_end >= self.test_start:
            raise ValueError("样本内训练期必须早于样本外测试期")
        return self


class BacktestOptimizationSummary(BaseModel):
    id: int
    name: str = ""
    status: BacktestResearchStatus | str
    strategy_key: str = ""
    train_start: str = ""
    train_end: str = ""
    test_start: str = ""
    test_end: str = ""
    optimization_target: str = "sharpe"
    search_method: str = "grid"
    progress_pct: float = 0.0
    owner_user_id: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None


class BacktestOptimizationDetail(BacktestOptimizationSummary):
    request: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    error_message: str = ""


class BacktestOptimizationListResponse(BaseModel):
    items: list[BacktestOptimizationSummary] = Field(default_factory=list)
    total: int = 0
    limit: int
    offset: int


class BacktestValidationCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    name: str = Field(default="", max_length=120)
    strategy: str = Field(..., min_length=1, max_length=80, alias="strategy_key")
    param_grid: dict[str, list[Any]] = Field(default_factory=default_walk_forward_param_grid)
    start_date: str = Field(..., min_length=8, max_length=16)
    end_date: str = Field(..., min_length=8, max_length=16)
    window_count: int = Field(default=4, ge=1, le=12)
    train_ratio: float = Field(default=0.75, gt=0.5, lt=0.95)
    optimization_target: OptimizationTarget = "sharpe"
    initial_cash: float = Field(default=100000.0, gt=0, alias="initial_capital")
    benchmark_symbol: str = Field(default="000300", max_length=24, alias="benchmark")
    execution_model: str = Field(default="conservative_slippage", max_length=40)
    max_combinations: int = Field(default=500, ge=1, le=500)

    @model_validator(mode="after")
    def validate_param_grid(self) -> "BacktestValidationCreate":
        self.param_grid = self.param_grid or default_walk_forward_param_grid()
        invalid = sorted(set(self.param_grid) - ALLOWED_OPTIMIZATION_PARAMS)
        if invalid:
            raise ValueError(f"不支持优化参数: {', '.join(invalid)}")
        for key, values in self.param_grid.items():
            if not isinstance(values, list) or not values:
                raise ValueError(f"{key} 必须提供非空取值列表")
        if self.start_date >= self.end_date:
            raise ValueError("验证日期范围无效")
        return self


class BacktestValidationSummary(BaseModel):
    id: int
    name: str = ""
    status: BacktestResearchStatus | str
    strategy_key: str = ""
    start_date: str = ""
    end_date: str = ""
    window_count: int = 0
    train_ratio: float = 0.0
    optimization_target: str = "sharpe"
    pbo_risk: str = ""
    downgrade_review: bool = False
    stability_conclusion: str = ""
    progress_pct: float = 0.0
    owner_user_id: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None


class BacktestValidationDetail(BacktestValidationSummary):
    request: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    error_message: str = ""


class BacktestValidationListResponse(BaseModel):
    items: list[BacktestValidationSummary] = Field(default_factory=list)
    total: int = 0
    limit: int
    offset: int


class BacktestResearchMutationResponse(BaseModel):
    ok: bool = True
    task_id: int
    status: str
    message: str = ""
