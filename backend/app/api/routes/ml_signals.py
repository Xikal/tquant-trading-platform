from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.admin_auth import require_admin_auth
from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.entities import User
from app.models.schema_defs.phase4 import (
    MLSignalArtifactStorageCheckResponse,
    MLSignalIncrementalTrainRequest,
    MLSignalModelOut,
    MLSignalPredictionRequest,
    MLSignalPredictionResponse,
    MLSignalModelListResponse,
    MLSignalOnlineLearningStatusResponse,
    MLSignalSampleBuildRequest,
    MLSignalTrainRequest,
    RuntimeTaskOut,
    StrategyCapacityRequest,
    StrategyCapacityResponse,
)
from app.api.routes.heavy_task_helpers import enqueue_runtime_task
from app.services.ml_signal import MLSignalService
from app.services.ml_signal.promotion_service import MLSignalPromotionService
from app.services.strategy_capacity import StrategyCapacityService

router = APIRouter(prefix="/ml/signals", dependencies=[Depends(get_current_user)])


@router.post("/samples", response_model=RuntimeTaskOut, status_code=status.HTTP_202_ACCEPTED)
def build_ml_signal_samples(
    payload: MLSignalSampleBuildRequest,
    _: None = Depends(require_admin_auth),
    db: Session = Depends(get_db),
) -> RuntimeTaskOut:
    return enqueue_runtime_task(
        db,
        task_type="ml_signal_build_samples",
        payload=payload.model_dump(mode="json"),
        priority=200,
        idempotency_key=f"ml_signal_build_samples:{payload.source}:{payload.limit}:{payload.persist}",
        max_attempts=2,
    )


@router.post("/train", response_model=RuntimeTaskOut, status_code=status.HTTP_202_ACCEPTED)
def train_ml_signal_model(
    payload: MLSignalTrainRequest,
    _: None = Depends(require_admin_auth),
    db: Session = Depends(get_db),
) -> RuntimeTaskOut:
    return enqueue_runtime_task(
        db,
        task_type="ml_signal_train",
        payload=payload.model_dump(mode="json"),
        priority=200,
        idempotency_key=f"ml_signal_train:{payload.model_key}:{payload.model_type}:{payload.source}:{payload.limit}:{payload.promote}",
        max_attempts=2,
    )


@router.post("/incremental-train", response_model=RuntimeTaskOut, status_code=status.HTTP_202_ACCEPTED)
def incremental_train_ml_signal_model(
    payload: MLSignalIncrementalTrainRequest,
    _: None = Depends(require_admin_auth),
    db: Session = Depends(get_db),
) -> RuntimeTaskOut:
    return enqueue_runtime_task(
        db,
        task_type="ml_signal_incremental_train",
        payload=payload.model_dump(mode="json"),
        priority=190,
        idempotency_key=f"ml_signal_incremental_train:{payload.model_type}:{payload.limit}:{payload.min_samples}:{payload.promote}",
        max_attempts=2,
    )


@router.get("/models", response_model=MLSignalModelListResponse)
def list_ml_signal_models(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> MLSignalModelListResponse:
    return MLSignalService(db).list_models(limit=limit)


@router.post("/models/{model_key}/approve-promotion", response_model=MLSignalModelOut)
def approve_ml_signal_model_promotion(
    model_key: str,
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_admin_auth),
    db: Session = Depends(get_db),
) -> MLSignalModelOut:
    try:
        return MLSignalPromotionService(db).approve(model_key, operator=current_user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/online-learning/status", response_model=MLSignalOnlineLearningStatusResponse)
def get_ml_signal_online_learning_status(
    min_samples: int = Query(default=100, ge=20, le=100000),
    _: None = Depends(require_admin_auth),
    db: Session = Depends(get_db),
) -> MLSignalOnlineLearningStatusResponse:
    return MLSignalService(db).online_learning_status(min_samples=min_samples)


@router.get("/artifact-storage/check", response_model=MLSignalArtifactStorageCheckResponse)
def check_ml_artifact_storage(
    _: None = Depends(require_admin_auth),
    db: Session = Depends(get_db),
) -> MLSignalArtifactStorageCheckResponse:
    return MLSignalService(db).check_artifact_storage()


@router.post("/predict", response_model=MLSignalPredictionResponse)
def predict_ml_signal(
    payload: MLSignalPredictionRequest,
    db: Session = Depends(get_db),
) -> MLSignalPredictionResponse:
    return MLSignalService(db).predict(payload)


@router.post("/capacity", response_model=StrategyCapacityResponse)
def evaluate_strategy_capacity(
    payload: StrategyCapacityRequest,
    _: None = Depends(require_admin_auth),
    db: Session = Depends(get_db),
) -> StrategyCapacityResponse:
    return StrategyCapacityService(db).evaluate(payload)
