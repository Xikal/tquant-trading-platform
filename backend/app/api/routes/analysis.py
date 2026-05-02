import logging

from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.timing import log_slow_call, monotonic_start
from app.models.schemas import AnalysisRequest
from app.services.analysis_service import AnalysisService

router = APIRouter()
logger = logging.getLogger(__name__)
analysis_service = AnalysisService()


@router.post("/analyze")
def analyze_symbol(payload: AnalysisRequest, db: Session = Depends(get_db)):
    started_at = monotonic_start()
    try:
        result = analysis_service.analyze(db, payload, persist=True)
        return result.model_dump()
    finally:
        log_slow_call(logger, "analysis.analyze", started_at, symbol=payload.symbol)


@router.post("/analyze/batch")
def analyze_batch(
    payloads: list[AnalysisRequest] = Body(...),
    db: Session = Depends(get_db),
):
    started_at = monotonic_start()
    try:
        results = analysis_service.analyze_batch(db, payloads)
        return [item.model_dump() for item in results]
    finally:
        log_slow_call(logger, "analysis.analyze_batch", started_at, count=len(payloads), threshold_seconds=5.0)
