from typing import Optional
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.admin_auth import require_admin_auth
from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.timing import log_slow_call, monotonic_start
from app.models.schemas import LowBuyTradeLifecycleUpdate
from app.services.low_buy.strategy_governance import build_low_buy_strategy_governance
from app.services.low_buy.shared import DEFAULT_PRODUCTION_LOW_BUY_STRATEGY
from app.services.low_buy_screener import LowBuyScreenerService
from app.services.market_data import DataSourceError

router = APIRouter(prefix="/screeners", dependencies=[Depends(get_current_user)])
logger = logging.getLogger(__name__)
low_buy_screener = LowBuyScreenerService()


@router.get("/low-buy/strategies")
def low_buy_strategy_governance_view(db: Session = Depends(get_db)):
    return build_low_buy_strategy_governance(db).model_dump()


@router.get("/low-buy")
def low_buy_screener_view(
    strategy: str = Query(DEFAULT_PRODUCTION_LOW_BUY_STRATEGY),
    limit: int = Query(16, ge=1, le=40),
    scan_limit: int = Query(48, ge=12, le=480),
    scan_mode: str = Query("full"),
    include_history: bool = Query(False),
    db: Session = Depends(get_db),
):
    started_at = monotonic_start()
    try:
        result = low_buy_screener.screen(
            db=db,
            strategy=strategy,
            limit=limit,
            scan_limit=scan_limit,
            include_history=include_history,
            scan_mode=scan_mode,
        )
    except DataSourceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"低吸选股运行失败: {exc}") from exc
    finally:
        log_slow_call(
            logger,
            "screeners.low_buy",
            started_at,
            strategy=strategy,
            limit=limit,
            scan_limit=scan_limit,
            scan_mode=scan_mode,
            include_history=include_history,
        )
    return result.model_dump()


@router.get("/low-buy/quotes")
def low_buy_quote_refresh_view(
    strategy: str = Query(DEFAULT_PRODUCTION_LOW_BUY_STRATEGY),
    symbols: str = Query(""),
    db: Session = Depends(get_db),
):
    started_at = monotonic_start()
    try:
        symbol_list = [item.strip() for item in symbols.split(",") if item.strip()]
        result = low_buy_screener.refresh_candidate_quotes(
            db=db,
            strategy=strategy,
            symbols=symbol_list,
        )
    except DataSourceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"低吸价格刷新失败: {exc}") from exc
    finally:
        log_slow_call(
            logger,
            "screeners.low_buy_quotes",
            started_at,
            strategy=strategy,
            symbol_count=len([item for item in symbols.split(",") if item.strip()]),
        )
    return {"items": {symbol: payload.model_dump() for symbol, payload in result.items()}}


@router.get("/low-buy/history")
def low_buy_history_view(
    strategy: str = Query(DEFAULT_PRODUCTION_LOW_BUY_STRATEGY),
    db: Session = Depends(get_db),
):
    started_at = monotonic_start()
    try:
        result = low_buy_screener.history(db=db, strategy=strategy)
    except DataSourceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"低吸历史加载失败: {exc}") from exc
    finally:
        log_slow_call(logger, "screeners.low_buy_history", started_at, strategy=strategy)
    return result.model_dump()


@router.get("/low-buy/priority-board")
def low_buy_priority_board_view(
    limit: int = Query(12, ge=3, le=30),
    db: Session = Depends(get_db),
):
    started_at = monotonic_start()
    try:
        result = low_buy_screener.priority_board(db=db, limit=limit)
    except DataSourceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"优先级榜加载失败: {exc}") from exc
    finally:
        log_slow_call(logger, "screeners.low_buy_priority_board", started_at, limit=limit)
    return result.model_dump()


@router.get("/low-buy/lifecycle")
def low_buy_lifecycle_view(
    strategy: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=300),
    sync: bool = Query(False),
    db: Session = Depends(get_db),
):
    started_at = monotonic_start()
    try:
        if sync:
            result = low_buy_screener.sync_trade_lifecycle(
                db=db,
                strategy=strategy,
                limit=limit,
            )
        else:
            result = low_buy_screener.list_trade_lifecycle(
                db=db,
                strategy=strategy,
                limit=limit,
            )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"交易生命周期加载失败: {exc}") from exc
    finally:
        log_slow_call(
            logger,
            "screeners.low_buy_lifecycle",
            started_at,
            strategy=strategy,
            limit=limit,
            sync=sync,
        )
    return {"items": [item.model_dump() for item in result]}


@router.patch("/low-buy/lifecycle/{symbol}")
def update_low_buy_lifecycle_view(
    symbol: str,
    payload: LowBuyTradeLifecycleUpdate,
    _: None = Depends(require_admin_auth),
    db: Session = Depends(get_db),
):
    started_at = monotonic_start()
    try:
        result = low_buy_screener.update_trade_lifecycle(
            db=db,
            symbol=symbol,
            payload=payload,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"交易生命周期更新失败: {exc}") from exc
    finally:
        log_slow_call(logger, "screeners.low_buy_lifecycle_update", started_at, symbol=symbol)
    if result is None:
        raise HTTPException(status_code=404, detail="未找到对应交易生命周期记录。")
    return result.model_dump()


@router.get("/low-buy/execution-backtest")
def low_buy_execution_backtest_view(
    strategy: str = Query(DEFAULT_PRODUCTION_LOW_BUY_STRATEGY),
    lookback_days: int = Query(60, ge=5, le=260),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    started_at = monotonic_start()
    try:
        result = low_buy_screener.execution_backtest(
            db=db,
            strategy=strategy,
            lookback_days=lookback_days,
            limit=limit,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"执行回测失败: {exc}") from exc
    finally:
        log_slow_call(
            logger,
            "screeners.low_buy_execution_backtest",
            started_at,
            strategy=strategy,
            lookback_days=lookback_days,
            limit=limit,
            threshold_seconds=5.0,
        )
    return result.model_dump()
