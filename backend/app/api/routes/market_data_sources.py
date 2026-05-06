from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.auth import get_current_user
from app.models.schema_defs.phase4 import DataSourceProbeResponse
from app.services.market.providers import DataSourceProbeService

router = APIRouter(prefix="/market/data-sources", dependencies=[Depends(get_current_user)])


@router.get("/health", response_model=DataSourceProbeResponse)
def market_data_source_health() -> DataSourceProbeResponse:
    return DataSourceProbeService().probe()
