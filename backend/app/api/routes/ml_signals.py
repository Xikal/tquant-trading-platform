from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.admin_auth import require_admin_auth
from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.schema_defs.phase4 import (
    MLSignalPredictionRequest,
    MLSignalPredictionResponse,
    MLSignalModelListResponse,
    MLSignalSampleBuildRequest,
    MLSignalSampleBuildResponse,
    MLSignalTrainRequest,
    MLSignalTrainResponse,
)
from app.services.ml_signal import MLSignalService

router = APIRouter(prefix="/ml/signals", dependencies=[Depends(get_current_user)])


@router.post("/samples", response_model=MLSignalSampleBuildResponse)
def build_ml_signal_samples(
    payload: MLSignalSampleBuildRequest,
    _: None = Depends(require_admin_auth),
    db: Session = Depends(get_db),
) -> MLSignalSampleBuildResponse:
    return MLSignalService(db).build_samples(payload)


@router.post("/train", response_model=MLSignalTrainResponse)
def train_ml_signal_model(
    payload: MLSignalTrainRequest,
    _: None = Depends(require_admin_auth),
    db: Session = Depends(get_db),
) -> MLSignalTrainResponse:
    try:
        return MLSignalService(db).train(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/models", response_model=MLSignalModelListResponse)
def list_ml_signal_models(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> MLSignalModelListResponse:
    return MLSignalService(db).list_models(limit=limit)


@router.post("/predict", response_model=MLSignalPredictionResponse)
def predict_ml_signal(
    payload: MLSignalPredictionRequest,
    db: Session = Depends(get_db),
) -> MLSignalPredictionResponse:
    return MLSignalService(db).predict(payload)
