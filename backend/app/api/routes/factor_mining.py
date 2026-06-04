from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.admin_auth import require_admin_auth
from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.role_permissions import has_permission
from app.models.entities import User
from app.models.schema_defs.factor_mining import (
    FactorCodeSynthRequest,
    FactorCodeSynthResponse,
    FactorCreateRequest,
    FactorDefinitionOut,
    FactorEvaluationRequest,
    FactorEvaluationResponse,
    FactorHypothesisRequest,
    FactorHypothesisResponse,
    FactorIterationRequest,
    FactorIterationResponse,
    FactorListResponse,
    FactorPromoteRequest,
)
from app.models.schema_defs.phase4 import RuntimeTaskCreate, RuntimeTaskOut
from app.api.routes.heavy_task_helpers import enqueue_runtime_task
from app.services.factor_mining.code_synth_agent import FactorCodeSynthAgent
from app.services.factor_mining.combination import ic_weighted_combination, ridge_regression_combination
from app.services.factor_mining.health import FactorHealthService
from app.services.factor_mining.library import FactorLibrary
from app.services.factor_mining.orchestrator import FactorMiningOrchestrator
from app.services.factor_mining.runtime_values import is_factor_active, set_factor_active
from app.services.operation_audit import record_operation_audit
from app.services.tasks import RuntimeTaskQueue


def _require_factor_research_permission(current_user: User = Depends(get_current_user)) -> User:
    if has_permission(current_user, "research") or has_permission(current_user, "strategy_config"):
        return current_user
    raise HTTPException(status_code=403, detail="账号未开通因子研究权限")


router = APIRouter(prefix="/factor-mining", dependencies=[Depends(_require_factor_research_permission)])


@router.get("/factors", response_model=FactorListResponse)
def list_factors(
    status: str = Query(default="", max_length=24),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> FactorListResponse:
    return FactorLibrary(db).list(status=status, limit=limit, offset=offset)


@router.post("/factors", response_model=FactorDefinitionOut)
def create_factor(
    payload: FactorCreateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FactorDefinitionOut:
    try:
        result = FactorLibrary(db).create(payload, user=current_user)
        record_operation_audit(
            db,
            operation="factor_mining_create",
            user=current_user,
            resource_type="factor_definition",
            resource_id=result.factor_key,
            operator_ip=_client_ip(request),
            detail={"category": result.category, "source": result.source},
        )
        db.commit()
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/hypotheses", response_model=FactorHypothesisResponse)
def generate_hypotheses(
    payload: FactorHypothesisRequest,
    db: Session = Depends(get_db),
) -> FactorHypothesisResponse:
    return FactorMiningOrchestrator(db).hypotheses(
        topic=payload.topic,
        count=payload.count,
        use_llm=payload.use_llm,
    )


@router.post("/code-synth", response_model=FactorCodeSynthResponse)
def synthesize_factor_code(
    payload: FactorCodeSynthRequest,
    db: Session = Depends(get_db),
) -> FactorCodeSynthResponse:
    return FactorCodeSynthAgent(db).synthesize(payload)


@router.post("/factors/{factor_key}/evaluate", response_model=RuntimeTaskOut, status_code=status.HTTP_202_ACCEPTED)
def evaluate_factor(
    factor_key: str,
    payload: FactorEvaluationRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RuntimeTaskOut:
    task = enqueue_runtime_task(
        db,
        task_type="factor_mining_evaluate",
        payload={"factor_key": factor_key, "evaluation": payload.model_dump(mode="json"), "operator_ip": _client_ip(request)},
        priority=220,
        idempotency_key=f"factor_mining_evaluate:{factor_key}:{payload.holding_days}:{payload.limit_symbols}:{payload.min_cross_section}",
        max_attempts=2,
    )
    record_operation_audit(
        db,
        operation="factor_mining_evaluate_queued",
        user=current_user,
        resource_type="factor_definition",
        resource_id=factor_key,
        operator_ip=_client_ip(request),
        detail={"task_id": task.id},
    )
    db.commit()
    return task


@router.post("/factors/{factor_key}/promote", response_model=FactorDefinitionOut)
def promote_factor(
    factor_key: str,
    payload: FactorPromoteRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_admin_auth),
    db: Session = Depends(get_db),
) -> FactorDefinitionOut:
    try:
        result = FactorLibrary(db).promote(
            factor_key,
            target_status=payload.target_status,
            reason=payload.reason,
            user=current_user,
        )
        record_operation_audit(
            db,
            operation="factor_mining_promote",
            user=current_user,
            resource_type="factor_definition",
            resource_id=factor_key,
            operator_ip=_client_ip(request),
            detail={"target_status": payload.target_status, "reason": payload.reason},
        )
        db.commit()
        return result
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/factors/{factor_key}/activation")
def get_factor_activation(factor_key: str) -> dict:
    return {"factor_key": factor_key, "active": is_factor_active(factor_key)}


@router.put("/factors/{factor_key}/activation")
def update_factor_activation(
    factor_key: str,
    payload: dict,
    request: Request,
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_admin_auth),
    db: Session = Depends(get_db),
) -> dict:
    active = bool(payload.get("active"))
    set_factor_active(db, factor_key, active)
    record_operation_audit(
        db,
        operation="factor_mining_activation",
        user=current_user,
        resource_type="factor_definition",
        resource_id=factor_key,
        operator_ip=_client_ip(request),
        detail={"active": active},
    )
    db.commit()
    return {"factor_key": factor_key, "active": active}


@router.post("/iterate", response_model=RuntimeTaskOut, status_code=status.HTTP_202_ACCEPTED)
def iterate_factor(
    payload: FactorIterationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RuntimeTaskOut:
    task = enqueue_runtime_task(
        db,
        task_type="factor_mining_iterate",
        payload=payload.model_dump(mode="json"),
        priority=220,
        idempotency_key=f"factor_mining_iterate:{current_user.id}:{payload.hypothesis.factor_key}:{payload.rounds}",
        max_attempts=2,
    )
    return task


@router.post("/tasks/evaluate", response_model=RuntimeTaskOut)
def enqueue_factor_evaluation_task(
    payload: dict,
    _: None = Depends(require_admin_auth),
    db: Session = Depends(get_db),
) -> RuntimeTaskOut:
    factor_key = str(payload.get("factor_key") or "").strip()
    if not factor_key:
        raise HTTPException(status_code=400, detail="factor_key required")
    return RuntimeTaskQueue(db).enqueue(
        RuntimeTaskCreate(
            task_type="factor_mining_evaluate",
            payload=payload,
            priority=220,
            idempotency_key=f"factor_mining_evaluate:{factor_key}:{payload.get('end_date') or ''}",
            max_attempts=2,
        )
    )


@router.get("/health")
def factor_health_dashboard(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict:
    return FactorHealthService(db).dashboard(limit=limit)


@router.post("/combine")
def combine_factor_weights(payload: dict) -> dict:
    method = str(payload.get("method") or "ic_weighted").strip().lower()
    if method in {"ridge", "ridge_regression"}:
        factor_returns = payload.get("factor_returns")
        target_returns = payload.get("target_returns")
        if not isinstance(factor_returns, dict) or not isinstance(target_returns, list):
            raise HTTPException(status_code=400, detail="factor_returns and target_returns required for ridge")
        result = ridge_regression_combination(
            factor_returns,
            target_returns,
            alpha=float(payload.get("alpha") or 1.0),
        )
    else:
        metrics = payload.get("metrics_by_factor")
        if not isinstance(metrics, dict):
            raise HTTPException(status_code=400, detail="metrics_by_factor required")
        result = ic_weighted_combination(metrics)
    return {"weights": result.weights, "method": result.method, "warning": result.warning}


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    return request.client.host if request.client else ""
