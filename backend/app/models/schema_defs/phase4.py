from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


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
    params: dict[str, Any] = Field(default_factory=dict)
    description: str = ""
    activate: bool = True


class QuantParameterSetOut(BaseModel):
    id: int
    version: str
    name: str = ""
    scope: str = "low_buy"
    status: str = "active"
    params: dict[str, Any] = Field(default_factory=dict)
    description: str = ""
    created_by: str = "system"
    created_at: datetime
    activated_at: Optional[datetime] = None


class QuantParameterSetListResponse(BaseModel):
    current_version: str = ""
    items: list[QuantParameterSetOut] = Field(default_factory=list)


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
    model_type: Literal["logistic", "xgboost", "lightgbm"] = "xgboost"
    source: Literal["paper", "backtest", "combined"] = "combined"
    limit: int = Field(default=5000, ge=20, le=100000)
    min_samples: int = Field(default=200, ge=20, le=100000)
    validation_ratio: float = Field(default=0.2, ge=0.05, le=0.5)
    promote: bool = False
    min_validation_accuracy: float = Field(default=0.55, ge=0.0, le=1.0)


class MLSignalTrainResponse(BaseModel):
    model_key: str
    model_type: str
    status: Literal["research", "production", "failed"] = "research"
    sample_count: int = 0
    feature_names: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    artifact_uri: str = ""
    warning: str = ""


class MLSignalModelOut(BaseModel):
    model_key: str
    model_type: str
    status: str
    feature_names: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    artifact_uri: str = ""
    created_at: datetime


class MLSignalModelListResponse(BaseModel):
    items: list[MLSignalModelOut] = Field(default_factory=list)
    production_model_key: str = ""


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
