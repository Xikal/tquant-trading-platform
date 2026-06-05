import logging
import re
from typing import Union

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.rate_limit import require_analysis_batch_rate_limit
from app.core.timing import log_slow_call, monotonic_start
from app.models.schemas import AnalysisRequest, AnalysisResponse, RuntimeTaskOut
from app.api.routes.heavy_task_helpers import enqueue_runtime_task, queued_task_response
from app.services.analysis_service import AnalysisService

router = APIRouter(dependencies=[Depends(get_current_user)])
logger = logging.getLogger(__name__)
analysis_service = AnalysisService()
_SYMBOL_PATTERN = re.compile(r"^\d{6}$")
_MAX_BATCH_SIZE = 10


@router.post("/analyze", response_model=AnalysisResponse)
def analyze_symbol(payload: AnalysisRequest, db: Session = Depends(get_db)):
    started_at = monotonic_start()
    try:
        result = analysis_service.analyze(db, payload, persist=True)
        return result.model_dump()
    finally:
        log_slow_call(logger, "analysis.analyze", started_at, symbol=payload.symbol)


@router.post("/analyze/batch", response_model=Union[list[AnalysisResponse], RuntimeTaskOut])
def analyze_batch(
    request: Request,
    payloads: list[AnalysisRequest] = Body(...),
    queue: bool = False,
    db: Session = Depends(get_db),
):
    require_analysis_batch_rate_limit(request)
    _validate_batch_payload(payloads)
    if queue:
        return queued_task_response(
            enqueue_runtime_task(
                db,
                task_type="analysis_batch",
                payload={"items": [item.model_dump(mode="json") for item in payloads]},
                priority=170,
                idempotency_key=f"analysis_batch:{','.join(item.symbol for item in payloads)}",
                max_attempts=2,
            )
        )
    started_at = monotonic_start()
    try:
        results = analysis_service.analyze_batch(db, payloads)
        return [item.model_dump() for item in results]
    finally:
        log_slow_call(logger, "analysis.analyze_batch", started_at, count=len(payloads), threshold_seconds=5.0)


def _validate_batch_payload(payloads: list[AnalysisRequest]) -> None:
    if not payloads:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="批量分析至少需要 1 个标的。",
        )
    if len(payloads) > _MAX_BATCH_SIZE:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"批量分析最多支持 {_MAX_BATCH_SIZE} 个标的。",
        )
    invalid_symbols = [item.symbol for item in payloads if not _SYMBOL_PATTERN.fullmatch((item.symbol or "").strip())]
    if invalid_symbols:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="批量分析股票代码必须为 6 位数字。",
        )
