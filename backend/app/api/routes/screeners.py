from typing import Optional
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.routes.frontend_next_audit import record_frontend_next_audit, stable_hash
from app.core.admin_auth import require_admin_auth
from app.core.auth import get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.core.role_permissions import is_admin_user
from app.core.timing import log_slow_call, monotonic_start
from app.models.entities import LowBuyTradeLifecycleSnapshot, User
from app.models.schemas import LowBuyTradeLifecycleUpdate
from app.models.schema_defs.late_session_board import LateSessionBoardResponse
from app.models.schema_defs.screener import LowBuyStrategyGovernanceUpdate
from app.api.routes.heavy_task_helpers import enqueue_runtime_task, queued_task_response
from app.services.low_buy.strategy_governance import build_low_buy_strategy_governance, set_strategy_governance_override
from app.services.low_buy.late_session_board import build_late_session_board_from_priority_response
from app.services.low_buy.late_session_cache import (
    late_session_cache_key,
    load_distributed_late_session_board_snapshot,
    user_filter_hash,
)
from app.services.low_buy.late_session_tasks import late_session_idempotency_key
from app.services.low_buy.late_session_policy import LATE_SESSION_SOURCE_CANDIDATE_LIMIT
from app.services.low_buy.shared import DEFAULT_PRODUCTION_LOW_BUY_STRATEGY
from app.services.low_buy_screener import LowBuyScreenerService
from app.services.market_data import DataSourceError
from app.services.performance.read_model_metrics import record_response_payload
from app.services.read_models.live_quote_overlay import apply_priority_board_live_overlay
from app.services.user_sector_preferences import (
    UserSectorPreferenceService,
    filter_low_buy_history_response,
    filter_low_buy_screener_response,
    filter_priority_board_response_for_user,
)

router = APIRouter(prefix="/screeners", dependencies=[Depends(get_current_user)])
logger = logging.getLogger(__name__)
low_buy_screener = LowBuyScreenerService()


class LowBuyLifecycleSmokeFixtureRequest(BaseModel):
    symbol: str = Field(default="000001", max_length=16)
    name: str = Field(default="平安银行", max_length=64)
    strategy_key: str = Field(default="first_board", max_length=80)
    signal_trade_date: str = Field(default="2026-06-05", max_length=16)
    reason: str = Field(default="frontend-next rollback smoke", max_length=160)


@router.get("/low-buy/strategies")
def low_buy_strategy_governance_view(db: Session = Depends(get_db)):
    return build_low_buy_strategy_governance(db).model_dump()


@router.patch("/low-buy/strategies/{strategy_key}")
def low_buy_strategy_governance_update_view(
    strategy_key: str,
    payload: LowBuyStrategyGovernanceUpdate,
    request: Request,
    _: None = Depends(require_admin_auth),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        before = build_low_buy_strategy_governance(db).model_dump(mode="json")
        result = set_strategy_governance_override(
            db,
            strategy_key=strategy_key,
            status=payload.status,
            reason=payload.reason,
        )
        after = build_low_buy_strategy_governance(db).model_dump(mode="json")
        audit_id = record_frontend_next_audit(
            db,
            request=request,
            operation="frontend_next.low_buy_strategy_governance_update",
            user=current_user,
            resource_type="low_buy_strategy_governance",
            resource_id=strategy_key,
            detail={
                "strategy_key": strategy_key,
                "target_state": payload.status,
                "reason": payload.reason,
                "before_hash": stable_hash(before),
                "after_hash": stable_hash(after),
            },
        )
        db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"策略治理更新失败: {exc}") from exc
    return {**result.model_dump(), "audit_id": audit_id, "before_hash": stable_hash(before), "after_hash": stable_hash(after)}


@router.get("/low-buy")
def low_buy_screener_view(
    strategy: str = Query(DEFAULT_PRODUCTION_LOW_BUY_STRATEGY),
    limit: int = Query(16, ge=1, le=40),
    scan_limit: int = Query(48, ge=12, le=480),
    scan_mode: str = Query("full"),
    include_history: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    started_at = monotonic_start()
    try:
        if _low_buy_screen_requires_queue(scan_mode=scan_mode, scan_limit=scan_limit):
            return queued_task_response(
                enqueue_runtime_task(
                    db,
                    task_type="low_buy_materialization_refresh",
                    payload={"strategies": [strategy], "limit": limit, "scan_limit": scan_limit, "source": "screeners.low_buy"},
                    priority=120,
                    idempotency_key=f"low_buy_materialization_refresh:{strategy}:{scan_limit}",
                    max_attempts=2,
                )
            )
        result = low_buy_screener.screen(
            db=db,
            strategy=strategy,
            limit=limit,
            scan_limit=scan_limit,
            include_history=include_history,
            scan_mode=scan_mode,
        )
        excluded = UserSectorPreferenceService(db).get_excluded_sector_set(current_user.id)
        result = filter_low_buy_screener_response(result, excluded)
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    started_at = monotonic_start()
    try:
        result = low_buy_screener.history(db=db, strategy=strategy)
        excluded = UserSectorPreferenceService(db).get_excluded_sector_set(current_user.id)
        result = filter_low_buy_history_response(result, excluded)
    except DataSourceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"低吸历史加载失败: {exc}") from exc
    finally:
        log_slow_call(logger, "screeners.low_buy_history", started_at, strategy=strategy)
    return result.model_dump()


@router.get("/low-buy/priority-board")
def low_buy_priority_board_view(
    request: Request,
    limit: int = Query(12, ge=3, le=30),
    refresh: str = Query("cache", pattern="^(cache|async|sync)$"),
    strategy_variant: str = Query("baseline", pattern="^(baseline|front_row_weighted|front_row_only)$"),
    front_row_only: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    started_at = monotonic_start()
    effective_refresh = _priority_board_refresh_mode_for_web(
        request=request,
        current_user=current_user,
        refresh=refresh,
    )
    try:
        result = low_buy_screener.priority_board(
            db=db,
            limit=limit,
            refresh_mode=effective_refresh,
            front_row_only=front_row_only,
            strategy_variant=strategy_variant,
        )
        excluded = UserSectorPreferenceService(db).get_excluded_sector_set(current_user.id)
        result = filter_priority_board_response_for_user(result, user_id=current_user.id, excluded_sectors=excluded)
        result = apply_priority_board_live_overlay(result)
        record_response_payload("priority_board", result, item_count=len(result.items))
    except DataSourceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"优先级榜加载失败: {exc}") from exc
    finally:
        log_slow_call(
            logger,
            "screeners.low_buy_priority_board",
            started_at,
            limit=limit,
            refresh=refresh,
            effective_refresh=effective_refresh,
            front_row_only=front_row_only,
            strategy_variant=strategy_variant,
        )
    return result.model_dump()


@router.get("/low-buy/late-session-board", response_model=LateSessionBoardResponse)
def low_buy_late_session_board_view(
    request: Request,
    limit: int = Query(12, ge=3, le=30),
    slot: str = Query("latest", pattern="^(preview_1450|snapshot_1455|final_1457|latest)$"),
    refresh: str = Query("cache", pattern="^(cache|async|sync)$"),
    strategy_variant: str = Query("baseline", pattern="^(baseline|front_row_weighted|front_row_only)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    started_at = monotonic_start()
    effective_refresh = _late_session_refresh_mode_for_web(
        request=request,
        current_user=current_user,
        refresh=refresh,
    )
    try:
        source_board = low_buy_screener.priority_board(
            db=db,
            limit=LATE_SESSION_SOURCE_CANDIDATE_LIMIT,
            refresh_mode="cache",
            strategy_variant=strategy_variant,
        )
        excluded = UserSectorPreferenceService(db).get_excluded_sector_set(current_user.id)
        source_board = filter_priority_board_response_for_user(source_board, user_id=current_user.id, excluded_sectors=excluded)
        cached_result = (
            _load_late_session_board_cache(
                source_board,
                slot=slot,
                strategy_variant=strategy_variant,
                excluded_sectors=excluded,
            )
            if effective_refresh == "cache"
            else None
        )
        if cached_result is not None:
            result = cached_result
        elif effective_refresh == "async":
            enqueue_runtime_task(
                db,
                task_type="late_session_recommendation_refresh",
                payload={
                    "slot": slot,
                    "strategy_variant": strategy_variant,
                    "limit": limit,
                    "source_limit": LATE_SESSION_SOURCE_CANDIDATE_LIMIT,
                    "reason": "api_async",
                },
                priority=110,
                idempotency_key=late_session_idempotency_key(source_board.latest_trade_date, slot),
                max_attempts=2,
            )
            result = build_late_session_board_from_priority_response(
                source_board,
                slot=slot,
                limit=limit,
                refresh_mode=effective_refresh,
            )
            if not result.degradation_reason:
                result = result.model_copy(update={"degradation_reason": "refresh_queued"})
        else:
            result = build_late_session_board_from_priority_response(
                source_board,
                slot=slot,
                limit=limit,
                refresh_mode=effective_refresh,
            )
        record_response_payload("late_session_board", result, item_count=len(result.items))
    except DataSourceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"尾盘推荐榜加载失败: {exc}") from exc
    finally:
        log_slow_call(
            logger,
            "screeners.low_buy_late_session_board",
            started_at,
            limit=limit,
            slot=slot,
            refresh=refresh,
            effective_refresh=effective_refresh,
            strategy_variant=strategy_variant,
        )
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


@router.post("/low-buy/lifecycle/smoke-fixture")
def create_low_buy_lifecycle_smoke_fixture(
    payload: LowBuyLifecycleSmokeFixtureRequest,
    request: Request,
    _: None = Depends(require_admin_auth),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    marker = "frontend-next rollback smoke fixture"
    before = _smoke_fixture_snapshot(db, payload)
    row = db.execute(
        select(LowBuyTradeLifecycleSnapshot).where(
            LowBuyTradeLifecycleSnapshot.user_scope == "default",
            LowBuyTradeLifecycleSnapshot.signal_trade_date == payload.signal_trade_date,
            LowBuyTradeLifecycleSnapshot.strategy_key == payload.strategy_key,
            LowBuyTradeLifecycleSnapshot.symbol == payload.symbol,
        )
    ).scalars().first()
    created = row is None
    if created:
        row = LowBuyTradeLifecycleSnapshot(
            user_scope="default",
            signal_trade_date=payload.signal_trade_date,
            strategy_key=payload.strategy_key,
            symbol=payload.symbol,
        )
        db.add(row)
    row.name = payload.name
    row.signal_state = "watch"
    row.status = "planned"
    row.entry_plan_low = 10.0
    row.entry_plan_high = 10.5
    row.stop_loss = 9.5
    row.take_profit = 11.0
    row.max_holding_days = 5
    row.entry_price = None
    row.entry_trade_date = None
    row.exit_price = None
    row.exit_trade_date = None
    row.exit_reason = ""
    row.realized_return_pct = 0.0
    row.max_gain_pct = 0.0
    row.max_drawdown_pct = 0.0
    row.attribution_note = marker
    row.payload_json = '{"source":"frontend-next-write-rollback-smoke"}'
    db.flush()
    after = _smoke_fixture_snapshot(db, payload)
    audit_id = record_frontend_next_audit(
        db,
        request=request,
        operation="frontend_next.low_buy_lifecycle_smoke_fixture_create",
        user=current_user,
        resource_type="low_buy_lifecycle_smoke_fixture",
        resource_id=payload.symbol,
        detail={
            "symbol": payload.symbol,
            "strategy_key": payload.strategy_key,
            "signal_trade_date": payload.signal_trade_date,
            "created": created,
            "before_hash": stable_hash(before),
            "after_hash": stable_hash(after),
            "reason": payload.reason,
        },
    )
    db.commit()
    return {
        "ok": True,
        "created": created,
        "symbol": payload.symbol,
        "strategy_key": payload.strategy_key,
        "signal_trade_date": payload.signal_trade_date,
        "audit_id": audit_id,
        "before_hash": stable_hash(before),
        "after_hash": stable_hash(after),
    }


@router.delete("/low-buy/lifecycle/smoke-fixture/{symbol}")
def delete_low_buy_lifecycle_smoke_fixture(
    symbol: str,
    request: Request,
    signal_trade_date: str = Query(default="2026-06-05", max_length=16),
    strategy_key: str = Query(default="first_board", max_length=80),
    _: None = Depends(require_admin_auth),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    marker = "frontend-next rollback smoke fixture"
    before = [
        _lifecycle_row_snapshot(row)
        for row in db.execute(
            select(LowBuyTradeLifecycleSnapshot).where(
                LowBuyTradeLifecycleSnapshot.user_scope == "default",
                LowBuyTradeLifecycleSnapshot.signal_trade_date == signal_trade_date,
                LowBuyTradeLifecycleSnapshot.strategy_key == strategy_key,
                LowBuyTradeLifecycleSnapshot.symbol == symbol,
                LowBuyTradeLifecycleSnapshot.attribution_note == marker,
            )
        ).scalars().all()
    ]
    result = db.execute(
        delete(LowBuyTradeLifecycleSnapshot).where(
            LowBuyTradeLifecycleSnapshot.user_scope == "default",
            LowBuyTradeLifecycleSnapshot.signal_trade_date == signal_trade_date,
            LowBuyTradeLifecycleSnapshot.strategy_key == strategy_key,
            LowBuyTradeLifecycleSnapshot.symbol == symbol,
            LowBuyTradeLifecycleSnapshot.attribution_note == marker,
        )
    )
    audit_id = record_frontend_next_audit(
        db,
        request=request,
        operation="frontend_next.low_buy_lifecycle_smoke_fixture_delete",
        user=current_user,
        resource_type="low_buy_lifecycle_smoke_fixture",
        resource_id=symbol,
        detail={
            "symbol": symbol,
            "strategy_key": strategy_key,
            "signal_trade_date": signal_trade_date,
            "deleted_count": int(result.rowcount or 0),
            "before_hash": stable_hash(before),
            "after_hash": stable_hash([]),
        },
    )
    db.commit()
    return {"ok": True, "deleted_count": int(result.rowcount or 0), "audit_id": audit_id}


@router.patch("/low-buy/lifecycle/{symbol}")
def update_low_buy_lifecycle_view(
    symbol: str,
    payload: LowBuyTradeLifecycleUpdate,
    request: Request,
    _: None = Depends(require_admin_auth),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    started_at = monotonic_start()
    try:
        before_items = [
            item.model_dump(mode="json")
            for item in low_buy_screener.list_trade_lifecycle(
                db=db,
                strategy=payload.strategy_key,
                limit=300,
            )
        ]
        result = low_buy_screener.update_trade_lifecycle(
            db=db,
            symbol=symbol,
            payload=payload,
        )
        after_items = [
            item.model_dump(mode="json")
            for item in low_buy_screener.list_trade_lifecycle(
                db=db,
                strategy=payload.strategy_key,
                limit=300,
            )
        ]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"交易生命周期更新失败: {exc}") from exc
    finally:
        log_slow_call(logger, "screeners.low_buy_lifecycle_update", started_at, symbol=symbol)
    if result is None:
        raise HTTPException(status_code=404, detail="未找到对应交易生命周期记录。")
    audit_id = record_frontend_next_audit(
        db,
        request=request,
        operation="frontend_next.low_buy_lifecycle_update",
        user=current_user,
        resource_type="low_buy_lifecycle",
        resource_id=symbol,
        detail={
            "symbol": symbol,
            "strategy_key": payload.strategy_key,
            "status": payload.status,
            "signal_trade_date": payload.signal_trade_date,
            "before_hash": stable_hash(before_items),
            "after_hash": stable_hash(after_items),
        },
    )
    db.commit()
    return {**result.model_dump(), "audit_id": audit_id, "before_hash": stable_hash(before_items), "after_hash": stable_hash(after_items)}


def _smoke_fixture_snapshot(db: Session, payload: LowBuyLifecycleSmokeFixtureRequest) -> list[dict]:
    return [
        _lifecycle_row_snapshot(row)
        for row in db.execute(
            select(LowBuyTradeLifecycleSnapshot).where(
                LowBuyTradeLifecycleSnapshot.user_scope == "default",
                LowBuyTradeLifecycleSnapshot.signal_trade_date == payload.signal_trade_date,
                LowBuyTradeLifecycleSnapshot.strategy_key == payload.strategy_key,
                LowBuyTradeLifecycleSnapshot.symbol == payload.symbol,
            )
        ).scalars().all()
    ]


def _lifecycle_row_snapshot(row: LowBuyTradeLifecycleSnapshot) -> dict:
    return {
        "symbol": row.symbol,
        "strategy_key": row.strategy_key,
        "signal_trade_date": row.signal_trade_date,
        "status": row.status,
        "signal_state": row.signal_state,
        "attribution_note": row.attribution_note,
    }


@router.get("/low-buy/execution-backtest")
def low_buy_execution_backtest_view(
    strategy: str = Query(DEFAULT_PRODUCTION_LOW_BUY_STRATEGY),
    lookback_days: int = Query(60, ge=5, le=260),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    started_at = monotonic_start()
    try:
        return queued_task_response(
            enqueue_runtime_task(
                db,
                task_type="low_buy_execution_backtest",
                payload={"strategy": strategy, "lookback_days": lookback_days, "limit": limit},
                priority=190,
                idempotency_key=f"low_buy_execution_backtest:{strategy}:{lookback_days}:{limit}",
                max_attempts=2,
            )
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"执行回测入队失败: {exc}") from exc
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


def _low_buy_screen_requires_queue(*, scan_mode: str, scan_limit: int) -> bool:
    return scan_mode == "full" and int(scan_limit or 0) > 120


def _priority_board_refresh_mode_for_web(
    *,
    request: Request,
    current_user: User,
    refresh: str,
) -> str:
    requested = str(refresh or "cache").strip().lower()
    if requested != "sync":
        return requested if requested in {"cache", "async"} else "cache"
    if getattr(get_settings(), "priority_board_web_sync_refresh_enabled", False) and _priority_board_admin_allowed(
        request=request,
        current_user=current_user,
    ):
        return "sync"
    return "async"


def _late_session_refresh_mode_for_web(
    *,
    request: Request,
    current_user: User,
    refresh: str,
) -> str:
    requested = str(refresh or "cache").strip().lower()
    if requested != "sync":
        return requested if requested in {"cache", "async"} else "cache"
    if getattr(get_settings(), "late_session_board_web_sync_refresh_enabled", False) and _priority_board_admin_allowed(
        request=request,
        current_user=current_user,
    ):
        return "sync"
    return "async"


def _load_late_session_board_cache(
    priority_board,
    *,
    slot: str,
    strategy_variant: str,
    excluded_sectors: set[str],
) -> Optional[LateSessionBoardResponse]:
    epoch = ":".join(
        item
        for item in (
            str(getattr(priority_board, "latest_trade_date", "") or ""),
            str(getattr(priority_board, "updated_at", "") or ""),
            str(getattr(priority_board, "total_candidates", "") or ""),
        )
        if item
    )
    key = late_session_cache_key(
        trade_date=str(getattr(priority_board, "latest_trade_date", "") or ""),
        slot=slot,
        strategy_variant=strategy_variant,
        source_epoch=epoch,
        user_filter_hash=user_filter_hash(excluded_sectors),
    )
    cached = load_distributed_late_session_board_snapshot(key)
    if cached is None:
        return None
    return cached.model_copy(update={"refresh_mode": "cache"})


def _priority_board_admin_allowed(*, request: Request, current_user: User) -> bool:
    try:
        if is_admin_user(current_user):
            return True
    except Exception:
        pass
    try:
        require_admin_auth(
            request,
            x_admin_token=request.headers.get("X-Admin-Token"),
            authorization=request.headers.get("Authorization"),
        )
        return True
    except HTTPException:
        return False
    except Exception:
        return False
