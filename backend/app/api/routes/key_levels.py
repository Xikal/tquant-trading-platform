from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.schema_defs.key_levels import KeyLevelResult
from app.services.key_levels.engine import AKeyLevelEngine
from app.services.key_levels.materialization import (
    blocked_key_level_result,
    read_cached_key_level,
    stale_key_level_result,
)
from app.services.key_levels.linkage import apply_three_layer_linkage
from app.services.shared.feature_flags import feature_enabled

router = APIRouter(prefix="/key-levels", dependencies=[Depends(get_current_user)])


@router.get("/stock/{symbol}", response_model=KeyLevelResult)
def stock_key_levels(
    symbol: str,
    request: Request,
    trade_date: str = "",
    lookback_days: Annotated[int, Query(ge=20, le=240)] = 120,
    include_intraday: bool = False,
    threshold_pct: Annotated[float, Query(ge=0.1, le=3.0)] = 0.3,
    db: Session = Depends(get_db),
) -> KeyLevelResult:
    _reject_request_time_refresh(request)
    if not _enabled(db):
        return blocked_key_level_result(scope="stock", key=symbol, reason="AKeyLevel 功能开关关闭，关键位入口隐藏。")
    cached = read_cached_key_level(db, scope="stock", key=symbol, trade_date=trade_date.strip() or None)
    if cached:
        if include_intraday:
            return apply_three_layer_linkage(
                db,
                AKeyLevelEngine(db).with_intraday(cached, threshold_pct=threshold_pct),
                trade_date=trade_date.strip() or None,
            )
        return apply_three_layer_linkage(db, cached, trade_date=trade_date.strip() or None)
    return stale_key_level_result(scope="stock", key=symbol, reason="日线关键位缓存缺失，等待 worker 物化后展示。")


@router.get("/sector/{sector_key}", response_model=KeyLevelResult)
def sector_key_levels(
    sector_key: str,
    request: Request,
    trade_date: str = "",
    lookback_days: Annotated[int, Query(ge=20, le=240)] = 120,
    include_intraday: bool = False,
    db: Session = Depends(get_db),
) -> KeyLevelResult:
    _reject_request_time_refresh(request)
    if not _enabled(db):
        return blocked_key_level_result(scope="sector", key=sector_key, reason="AKeyLevel 功能开关关闭，关键位入口隐藏。")
    cached = read_cached_key_level(db, scope="sector", key=sector_key, trade_date=trade_date.strip() or None)
    if cached and not include_intraday:
        return cached
    return stale_key_level_result(scope="sector", key=sector_key, reason="板块关键位缓存缺失，等待 worker 物化后展示。")


@router.get("/market", response_model=KeyLevelResult)
def market_key_levels(
    request: Request,
    trade_date: str = "",
    lookback_days: Annotated[int, Query(ge=20, le=240)] = 120,
    include_intraday: bool = False,
    db: Session = Depends(get_db),
) -> KeyLevelResult:
    _reject_request_time_refresh(request)
    if not _enabled(db):
        return blocked_key_level_result(scope="market", key="market", reason="AKeyLevel 功能开关关闭，关键位入口隐藏。")
    cached = read_cached_key_level(db, scope="market", key="market", trade_date=trade_date.strip() or None)
    if cached and not include_intraday:
        return cached
    return stale_key_level_result(scope="market", key="market", reason="大盘关键位缓存缺失，等待 worker 物化后展示。")


@router.get("/intraday/{symbol}", response_model=KeyLevelResult)
def intraday_key_levels(symbol: str, request: Request, db: Session = Depends(get_db)) -> KeyLevelResult:
    _reject_request_time_refresh(request)
    if not _enabled(db):
        return blocked_key_level_result(scope="stock", key=symbol, reason="AKeyLevel 功能开关关闭，关键位入口隐藏。")
    cached = read_cached_key_level(db, scope="stock", key=symbol)
    if cached is None:
        return stale_key_level_result(scope="stock", key=symbol, reason="日线关键位缓存缺失，等待 worker 物化后展示。")
    return apply_three_layer_linkage(db, AKeyLevelEngine(db).with_intraday(cached), trade_date=cached.trade_date)


def _enabled(db: Session) -> bool:
    return feature_enabled(db, "a_key_level_engine_enabled", default=False)


def _reject_request_time_refresh(request: Request | None) -> None:
    if request is not None and "refresh" in request.query_params:
        raise HTTPException(status_code=422, detail="关键位重算必须走 runtime worker，不允许请求时同步刷新。")
