from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class AgentQualityIssueOut(BaseModel):
    code: str
    severity: Literal["info", "warning", "error"] = "warning"
    message: str


class AgentQualityScoreRequest(BaseModel):
    provider: str = "unknown"
    agent_id: str = ""
    trace_id: str = ""
    input_payload: dict[str, Any] = Field(default_factory=dict)
    output_payload: dict[str, Any] = Field(default_factory=dict)
    required_fields: list[str] = Field(default_factory=list)


class AgentQualityScoreResponse(BaseModel):
    trace_id: str = ""
    provider: str = "unknown"
    agent_id: str = ""
    score: float = 0.0
    passed: bool = False
    issues: list[AgentQualityIssueOut] = Field(default_factory=list)
    blocked: bool = False
    summary: str = ""


class DataSourceQualityOut(BaseModel):
    source: str
    ok: bool = False
    quality: Literal["ok", "degraded", "stale", "failed"] = "failed"
    latency_ms: int = 0
    is_stale: bool = False
    warning: str = ""


class DataSourceProbeResponse(BaseModel):
    updated_at: str
    provider_order: list[str] = Field(default_factory=list)
    items: list[DataSourceQualityOut] = Field(default_factory=list)
    summary: str = ""


class QuantParameterSetCreate(BaseModel):
    version: str = Field(min_length=1, max_length=80)
    name: str = Field(default="", max_length=120)
    scope: str = Field(default="low_buy", max_length=40)
    market_state_scope: str = Field(default="", max_length=40)
    params: dict[str, Any] = Field(default_factory=dict)
    description: str = ""
    activate: bool = True


class QuantParameterSetOut(BaseModel):
    id: int
    version: str
    name: str = ""
    scope: str = "low_buy"
    market_state_scope: str = ""
    status: str = "active"
    params: dict[str, Any] = Field(default_factory=dict)
    description: str = ""
    created_by: str = "system"
    created_at: datetime
    activated_at: Optional[datetime] = None


class QuantParameterSetListResponse(BaseModel):
    current_version: str = ""
    items: list[QuantParameterSetOut] = Field(default_factory=list)


class QuantParameterExportResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    current_version: str = ""
    exported_at: datetime
    params: dict[str, Any] = Field(default_factory=dict)
    parameter_schema: dict[str, Any] = Field(default_factory=dict, alias="schema")


class QuantParameterRollbackRequest(BaseModel):
    version: str = Field(min_length=1, max_length=80)
    scope: str = Field(default="global", max_length=40)
    market_state_scope: str = Field(default="", max_length=40)


class QuantParameterAuditOut(BaseModel):
    id: int
    action: str
    version: str = ""
    scope: str = "global"
    operator: str = ""
    before: dict[str, Any] = Field(default_factory=dict)
    after: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class QuantParameterAuditListResponse(BaseModel):
    items: list[QuantParameterAuditOut] = Field(default_factory=list)


class RuntimeTaskCreate(BaseModel):
    task_type: str = Field(min_length=1, max_length=80)
    payload: dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(default=100, ge=0, le=1000)
    idempotency_key: str = Field(default="", max_length=160)
    max_attempts: int = Field(default=3, ge=1, le=10)


class RuntimeTaskEventOut(BaseModel):
    id: int
    task_id: int
    event_type: str
    message: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class RuntimeTaskOut(BaseModel):
    id: int
    task_type: str
    status: str
    priority: int = 100
    payload: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    error_message: str = ""
    attempt_count: int = 0
    max_attempts: int = 3
    progress_pct: float = 0.0
    locked_by: str = ""
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class RuntimeTaskListResponse(BaseModel):
    items: list[RuntimeTaskOut] = Field(default_factory=list)
    total: int = 0
    limit: int = 50
    offset: int = 0


class MLSignalSampleBuildRequest(BaseModel):
    source: Literal["paper", "backtest", "combined"] = "combined"
    limit: int = Field(default=500, ge=1, le=5000)
    persist: bool = True


class MLSignalSampleBuildResponse(BaseModel):
    source: str
    generated: int = 0
    persisted: int = 0
    feature_names: list[str] = Field(default_factory=list)
    warning: str = ""


class MLSignalTrainRequest(BaseModel):
    model_key: str = Field(default="", max_length=120)
    model_type: Literal["logistic", "xgboost", "lightgbm"] = "logistic"
    source: Literal["paper", "backtest", "combined"] = "combined"
    limit: int = Field(default=5000, ge=20, le=100000)
    min_samples: int = Field(default=200, ge=100, le=100000)
    validation_ratio: float = Field(default=0.2, ge=0.05, le=0.5)
    promote: bool = False
    min_validation_accuracy: float = Field(default=0.55, ge=0.5, le=1.0)


class MLSignalTrainResponse(BaseModel):
    model_key: str
    model_type: str
    status: Literal["research", "production", "failed"] = "research"
    sample_count: int = 0
    feature_names: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    artifact_uri: str = ""
    remote_artifact_uri: str = ""
    artifact_checksum: str = ""
    warning: str = ""


class MLSignalModelOut(BaseModel):
    model_key: str
    model_type: str
    status: str
    feature_names: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    artifact_uri: str = ""
    remote_artifact_uri: str = ""
    artifact_checksum: str = ""
    created_at: datetime


class MLSignalModelListResponse(BaseModel):
    items: list[MLSignalModelOut] = Field(default_factory=list)
    production_model_key: str = ""


class MLSignalOnlineLearningStatusResponse(BaseModel):
    generated_at: str
    paper_sample_count: int = 0
    closed_trade_sample_count: int = 0
    positive_sample_count: int = 0
    negative_sample_count: int = 0
    ready_for_training: bool = False
    min_samples: int = 100
    feature_names: list[str] = Field(default_factory=list)
    sequence_feature_names: list[str] = Field(default_factory=list)
    latest_model: MLSignalModelOut | None = None
    production_model_key: str = ""
    latest_incremental_task_id: int | None = None
    latest_incremental_task_status: str = ""
    latest_incremental_task_progress_pct: float = 0.0
    latest_incremental_task_finished_at: datetime | None = None
    next_training_rule: str = "每周一 16:00 后由 runtime worker 自动触发一次 paper 增量训练。"
    warnings: list[str] = Field(default_factory=list)


class MLSignalPredictionRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=16)
    features: dict[str, Any] = Field(default_factory=dict)
    model_key: str = ""


class MLSignalPredictionResponse(BaseModel):
    symbol: str
    model_key: str
    model_type: str = "heuristic"
    research_only: bool = True
    probability: float = 0.0
    label: Literal["positive", "neutral", "negative"] = "neutral"
    confidence: float = 0.0
    reasons: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    warning: str = "研究模型输出，不进入生产交易建议。"


class MLSignalArtifactStorageCheckResponse(BaseModel):
    ok: bool
    configured: bool = False
    backend: str = "local"
    remote_dir: str = ""
    write_ok: bool = False
    read_ok: bool = False
    restore_ok: bool = False
    cleanup_ok: bool = False
    message: str = ""


class MLSignalIncrementalTrainRequest(MLSignalTrainRequest):
    model_key: str = Field(default="", max_length=120)
    source: Literal["paper"] = "paper"
    limit: int = Field(default=5000, ge=20, le=100000)
    min_samples: int = Field(default=100, ge=20, le=100000)
    promote: bool = False


class StrategyCapacityRequest(BaseModel):
    strategies: list[str] = Field(default_factory=list)
    start_date: str = ""
    end_date: str = ""
    capital_levels: list[float] = Field(default_factory=lambda: [500000.0, 1000000.0, 5000000.0])
    trade_limit: int = Field(default=5000, ge=100, le=100000)
    bar_limit: int = Field(default=20000, ge=100, le=500000)


class StrategyCapacityPoint(BaseModel):
    capital: float
    order_amount: float = 0.0
    participation_pct: float = 0.0
    expected_edge_pct: float = 0.0
    impact_model: str = "sqrt_market_impact"
    impact_assumption: str = ""
    average_daily_amount: float = 0.0
    volatility_pct: float = 0.0
    kyle_impact_pct: float = 0.0
    temporary_impact_pct: float = 0.0
    permanent_impact_pct: float = 0.0
    almgren_chriss_cost_pct: float = 0.0
    execution_slices: int = 1
    slice_participation_pct: float = 0.0
    impact_pct: float = 0.0
    impact_cost_pct: float = 0.0
    slippage_cost_pct: float = 0.0
    net_edge_pct: float = 0.0
    capacity_status: str = "未知"


class StrategyCapacityItem(BaseModel):
    strategy_key: str
    sample_count: int = 0
    symbol_count: int = 0
    avg_daily_amount: float = 0.0
    volatility_pct: float = 0.0
    base_edge_pct: float = 0.0
    kyle_lambda: float = 0.0
    impact_model: str = "sqrt_market_impact"
    curve: list[StrategyCapacityPoint] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class StrategyCapacityResponse(BaseModel):
    generated_at: str
    capital_levels: list[float] = Field(default_factory=list)
    items: list[StrategyCapacityItem] = Field(default_factory=list)
    assumptions: dict[str, Any] = Field(default_factory=dict)


class PaperBacktestComparisonRequest(BaseModel):
    backtest_run_id: int = Field(gt=0)
    account_id: Optional[int] = None
    deviation_threshold_pct: float = Field(default=20.0, ge=1.0, le=100.0)


class PaperBacktestComparisonResponse(BaseModel):
    account_id: int
    backtest_run_id: int
    comparison_date: str
    expected_return_pct: float = 0.0
    actual_return_pct: float = 0.0
    deviation_pct: float = 0.0
    alert: bool = False
    reason: str = ""
    detail: dict[str, Any] = Field(default_factory=dict)
