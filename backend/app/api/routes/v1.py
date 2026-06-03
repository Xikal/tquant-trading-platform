from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.agent_tools.registry import enabled_tool_definitions
from app.core.auth import get_current_user
from app.core.database import get_db
from app.services.low_buy.shared import DEFAULT_PRODUCTION_LOW_BUY_STRATEGY
from app.services.low_buy.strategy_governance import build_low_buy_strategy_governance
from app.services.low_buy_screener import LowBuyScreenerService
from app.services.market_data import DataSourceError
from app.services.performance.read_model_metrics import record_response_payload
from app.services.read_models.live_quote_overlay import apply_priority_board_live_overlay

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1", dependencies=[Depends(get_current_user)])
low_buy_screener = LowBuyScreenerService()


@router.get("/strategy/low-buy/strategies")
def v1_low_buy_strategy_governance(db: Session = Depends(get_db)) -> dict:
    return build_low_buy_strategy_governance(db).model_dump()


@router.get("/strategy/priority-board")
def v1_low_buy_priority_board(
    limit: int = Query(12, ge=3, le=30),
    db: Session = Depends(get_db),
) -> dict:
    try:
        result = apply_priority_board_live_overlay(low_buy_screener.priority_board(db=db, limit=limit))
        record_response_payload("v1_priority_board", result, item_count=len(result.items))
        return result.model_dump()
    except DataSourceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("v1 priority board failed")
        raise HTTPException(status_code=500, detail=f"优先级榜加载失败: {exc}") from exc


@router.get("/strategy/low-buy")
def v1_low_buy_screener(
    strategy: str = Query(DEFAULT_PRODUCTION_LOW_BUY_STRATEGY),
    limit: int = Query(16, ge=1, le=40),
    scan_limit: int = Query(48, ge=12, le=480),
    scan_mode: str = Query("full"),
    include_history: bool = Query(False),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return low_buy_screener.screen(
            db=db,
            strategy=strategy,
            limit=limit,
            scan_limit=scan_limit,
            include_history=include_history,
            scan_mode=scan_mode,
        ).model_dump()
    except DataSourceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("v1 low-buy screener failed")
        raise HTTPException(status_code=500, detail=f"低吸选股运行失败: {exc}") from exc


@router.get("/agent/tools")
def v1_agent_tools() -> dict:
    return {"items": [tool.model_dump() for tool in enabled_tool_definitions()]}
