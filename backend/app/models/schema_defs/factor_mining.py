from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

FactorStatus = Literal["candidate", "validated", "production", "archived", "rejected"]
FactorDirection = Literal["higher_better", "lower_better"]
FactorSource = Literal["llm_generated", "human_crafted", "local_template"]


class FactorEvalResultOut(BaseModel):
    ic_mean: float = 0.0
    ic_std: float = 0.0
    icir: float = 0.0
    ic_t_stat: float = 0.0
    half_life_days: int = 0
    top_quintile_return: float = 0.0
    spread_return: float = 0.0
    information_ratio: float = 0.0
    oos_ic_mean: float = 0.0
    is_oos_consistent: bool = False
    walk_forward_oos_ic_mean: float = 0.0
    walk_forward_window_count: int = 0
    walk_forward_positive_window_rate_pct: float = 0.0
    walk_forward_no_negative_windows: bool = False
    bootstrap_ci_lower: float = 0.0
    max_existing_factor_corr: float = 0.0
    max_existing_factor_key: str = ""
    passed_candidate_gate: bool = False
    passed_production_gate: bool = False
    sample_days: int = 0
    observation_count: int = 0
    symbol_count: int = 0
    warnings: list[str] = Field(default_factory=list)


class FactorDefinitionOut(BaseModel):
    id: int | None = None
    factor_key: str
    name: str
    hypothesis: str = ""
    formula_code: str = ""
    data_deps: list[str] = Field(default_factory=list)
    direction: FactorDirection = "higher_better"
    category: str = "price"
    status: FactorStatus = "candidate"
    source: FactorSource = "human_crafted"
    version: str = "v1"
    eval_result: FactorEvalResultOut | None = None
    created_by: str = "system"
    created_at: datetime | None = None
    updated_at: datetime | None = None


class FactorCreateRequest(BaseModel):
    factor_key: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=120)
    hypothesis: str = ""
    formula_code: str = Field(min_length=20)
    data_deps: list[str] = Field(default_factory=lambda: ["close_price", "volume"])
    direction: FactorDirection = "higher_better"
    category: str = Field(default="price", max_length=40)
    source: FactorSource = "human_crafted"


class FactorListResponse(BaseModel):
    items: list[FactorDefinitionOut] = Field(default_factory=list)
    total: int = 0


class FactorHypothesisRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=200)
    count: int = Field(default=20, ge=20, le=50)
    use_llm: bool = True


class FactorHypothesisOut(BaseModel):
    factor_name: str
    factor_key: str
    hypothesis: str
    data_deps: list[str] = Field(default_factory=list)
    direction: FactorDirection = "higher_better"
    category: str = "price"
    limitations: list[str] = Field(default_factory=list)
    source: str = "local_template"


class FactorHypothesisResponse(BaseModel):
    provider: str = "deepseek-v4-flash"
    items: list[FactorHypothesisOut] = Field(default_factory=list)
    warning: str = ""


class FactorCodeSynthRequest(BaseModel):
    hypothesis: FactorHypothesisOut
    use_llm: bool = True


class FactorCodeSynthResponse(BaseModel):
    factor_key: str
    formula_code: str
    unit_tests: list[str] = Field(default_factory=list)
    safety_passed: bool = True
    warning: str = ""


class FactorEvaluationRequest(BaseModel):
    start_date: str = ""
    end_date: str = ""
    holding_days: int = Field(default=5, ge=1, le=20)
    limit_symbols: int = Field(default=500, ge=20, le=6000)
    min_cross_section: int = Field(default=20, ge=5, le=500)


class FactorEvaluationResponse(BaseModel):
    factor: FactorDefinitionOut
    result: FactorEvalResultOut
    interpretation: dict[str, Any] = Field(default_factory=dict)
    run_id: int | None = None
    elapsed_seconds: float = 0.0


class FactorPromoteRequest(BaseModel):
    target_status: FactorStatus = "validated"
    reason: str = ""


class FactorIterationRequest(BaseModel):
    hypothesis: FactorHypothesisOut
    rounds: int = Field(default=3, ge=1, le=3)
    evaluation: FactorEvaluationRequest = Field(default_factory=FactorEvaluationRequest)


class FactorIterationResponse(BaseModel):
    rounds: list[FactorEvaluationResponse] = Field(default_factory=list)
    final_verdict: str = "reject"
