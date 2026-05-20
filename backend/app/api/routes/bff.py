from __future__ import annotations

import logging
from typing import Callable, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.routes.market import market_breadth, paired_hedge_research, sector_relative_strength
from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.paper_auth import require_paper_trading
from app.core.timezone import beijing_now_string
from app.models.entities import User
from app.models.schema_defs.bff import (
    BffManifestResponse,
    BffPartialError,
    PaperWorkspaceBffResponse,
    StrategyWorkspaceBffResponse,
)
from app.models.schema_defs.market import (
    MarketBreadthResponse,
    PairedHedgeResearchResponse,
    SectorRelativeStrengthResponse,
)
from app.models.schema_defs.monitor import MonitorSnapshotResponse
from app.services.bff.paper_workspace import build_paper_workspace
from app.services.bff.strategy_workspace import build_strategy_workspace
from app.services.monitor_snapshot_service import build_monitor_snapshot

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/bff/v1", dependencies=[Depends(get_current_user)])
T = TypeVar("T")


class MonitorWorkspaceBffResponse(BaseModel):
    api_version: str = "v1"
    generated_at: str
    monitor_snapshot: MonitorSnapshotResponse | None = None
    market_breadth: MarketBreadthResponse | None = None
    sector_relative_strength: SectorRelativeStrengthResponse | None = None
    paired_hedge: PairedHedgeResearchResponse | None = None
    partial_errors: list[BffPartialError] = Field(default_factory=list)


@router.get("/manifest", response_model=BffManifestResponse)
def bff_manifest() -> BffManifestResponse:
    """Expose the stable BFF contract consumed by Web/App frontends."""

    return BffManifestResponse(
        modules=[
            "auth",
            "market",
            "strategy",
            "trade",
            "factor",
            "monitor",
        ]
    )


@router.get("/workspace/monitor", response_model=MonitorWorkspaceBffResponse)
def monitor_workspace_bff(
    priority_limit: int = Query(default=12, ge=1, le=30),
    sector_limit: int = Query(default=8, ge=1, le=20),
    per_sector_limit: int = Query(default=8, ge=1, le=30),
    hedge_limit: int = Query(default=4, ge=1, le=20),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MonitorWorkspaceBffResponse:
    """Aggregate monitor first-screen data behind a frontend-specific seam."""

    errors: list[BffPartialError] = []
    return MonitorWorkspaceBffResponse(
        generated_at=beijing_now_string(),
        monitor_snapshot=_safe(
            "monitor_snapshot",
            errors,
            lambda: build_monitor_snapshot(db, current_user=current_user, priority_limit=priority_limit),
        ),
        market_breadth=_safe("market_breadth", errors, market_breadth),
        sector_relative_strength=_safe(
            "sector_relative_strength",
            errors,
            lambda: sector_relative_strength(sector_limit, per_sector_limit, db),
        ),
        paired_hedge=_safe(
            "paired_hedge",
            errors,
            lambda: paired_hedge_research(hedge_limit, current_user, db),
        ),
        partial_errors=errors,
    )


@router.get("/workspace/paper", response_model=PaperWorkspaceBffResponse)
def paper_workspace_bff(
    order_limit: int = Query(default=80, ge=1, le=200),
    trade_limit: int = Query(default=300, ge=1, le=300),
    run_limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_paper_trading),
    db: Session = Depends(get_db),
) -> PaperWorkspaceBffResponse:
    """Aggregate the paper trading first-screen payload for Web/App clients."""

    return build_paper_workspace(
        db,
        current_user=current_user,
        order_limit=order_limit,
        trade_limit=trade_limit,
        run_limit=run_limit,
    )


@router.get("/workspace/strategy", response_model=StrategyWorkspaceBffResponse)
def strategy_workspace_bff(
    run_limit: int = Query(default=8, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StrategyWorkspaceBffResponse:
    """Aggregate StrategyHub first-screen data for Web/App clients."""

    return build_strategy_workspace(db, current_user=current_user, run_limit=run_limit)


def _safe(source: str, errors: list[BffPartialError], loader: Callable[[], T]) -> T | None:
    try:
        return loader()
    except HTTPException as exc:
        errors.append(BffPartialError(source=source, detail=str(exc.detail)))
        return None
    except Exception as exc:
        logger.warning("bff source failed source=%s", source, exc_info=(type(exc), exc, exc.__traceback__))
        errors.append(BffPartialError(source=source, detail="数据暂时不可用"))
        return None
