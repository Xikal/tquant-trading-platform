from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.schema_defs.strategy_meta import StrategyMetaResponse, StrategyPresetResponse, SymbolSearchResponse
from app.services.strategy_metadata_service import StrategyMetadataService

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/strategies/meta", response_model=StrategyMetaResponse)
def list_strategy_meta(db: Session = Depends(get_db)) -> StrategyMetaResponse:
    return StrategyMetadataService(db).list_strategy_meta()


@router.get("/strategy/presets", response_model=StrategyPresetResponse)
def list_strategy_presets(db: Session = Depends(get_db)) -> StrategyPresetResponse:
    return StrategyMetadataService(db).list_presets()


@router.get("/symbols/search", response_model=SymbolSearchResponse)
def search_symbols(
    q: str = Query(default="", min_length=0, max_length=40),
    limit: int = Query(default=10, ge=1, le=20),
    db: Session = Depends(get_db),
) -> SymbolSearchResponse:
    return StrategyMetadataService(db).search_symbols(q, limit)
