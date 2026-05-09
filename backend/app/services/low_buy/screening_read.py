from __future__ import annotations

from typing import Any

from app.services.low_buy.recommendation_duration import attach_response_recommendation_durations
from app.services.low_buy.screening_helpers import build_pending_full_response
from app.services.low_buy.shared import (
    DataSourceError,
    DEFAULT_PRODUCTION_LOW_BUY_STRATEGY,
    LowBuyScreenerResponse,
    PERFORMANCE_LOOKBACK_DAYS,
    Session,
)


def screen_read_path(
    owner: Any,
    db: Session,
    *,
    strategy: str = DEFAULT_PRODUCTION_LOW_BUY_STRATEGY,
    limit: int = 16,
    scan_limit: int = 72,
    include_history: bool = False,
    scan_mode: str = "quick",
) -> LowBuyScreenerResponse:
    if scan_mode not in {"quick", "full"}:
        raise DataSourceError(f"未知扫描模式: {scan_mode}")
    trade_dates = owner._get_recent_trade_dates(14)
    if len(trade_dates) < 3:
        raise DataSourceError("交易日历数据不足，暂时无法运行低吸选股。")
    latest_completed_trade_date = owner._resolve_latest_completed_trade_date(trade_dates)
    latest_trade_date = owner._resolve_active_structure_trade_date(
        trade_dates=trade_dates,
        latest_completed_trade_date=latest_completed_trade_date,
    )
    cached_full = owner._load_cached_full_result(
        db=db,
        strategy=strategy,
        latest_trade_date=latest_trade_date,
        limit=limit,
        include_history=include_history,
    )
    if scan_mode == "full" and cached_full is not None:
        return _full_cached_response(
            owner,
            db=db,
            payload=cached_full,
            latest_completed_trade_date=latest_completed_trade_date,
        )

    full_in_progress = owner._is_full_scan_running(
        strategy=strategy,
        latest_trade_date=latest_trade_date,
        limit=limit,
        include_history=include_history,
    )

    if scan_mode == "full":
        return _full_or_pending_response(
            owner,
            db=db,
            strategy=strategy,
            latest_trade_date=latest_trade_date,
            latest_completed_trade_date=latest_completed_trade_date,
            limit=limit,
            scan_limit=scan_limit,
            include_history=include_history,
            full_in_progress=full_in_progress,
        )

    latest_snapshot = owner._load_latest_materialized_full_result_on_or_before(
        db=db,
        strategy=strategy,
        latest_trade_date=latest_completed_trade_date,
        limit=limit,
        include_history=include_history,
        allow_repair=False,
    )
    if latest_snapshot is not None:
        latest_snapshot = owner._attach_strategy_performance(
            db=db,
            payload=latest_snapshot,
            build_if_missing=False,
        )
        latest_snapshot = owner._attach_close_review_snapshot(
            db=db,
            payload=latest_snapshot,
            review_trade_date=latest_completed_trade_date,
            build_if_missing=False,
        )
        return latest_snapshot.model_copy(
            update={
                "requested_mode": scan_mode,
                "response_mode": "full",
                "full_scan_ready": True,
                "full_scan_in_progress": full_in_progress,
                "full_scan_updated_at": latest_snapshot.full_scan_updated_at or latest_snapshot.as_of_date,
            }
        )

    pending = _pending_response(
        owner,
        db=db,
        strategy=strategy,
        latest_trade_date=latest_trade_date,
        latest_completed_trade_date=latest_completed_trade_date,
        scan_limit=scan_limit,
        full_scan_in_progress=full_in_progress,
    )
    return pending.model_copy(update={"requested_mode": scan_mode, "response_mode": "pending"})


def _full_cached_response(owner: Any, *, db: Session, payload: LowBuyScreenerResponse, latest_completed_trade_date: str) -> LowBuyScreenerResponse:
    payload = owner._attach_strategy_performance(db=db, payload=payload, build_if_missing=False)
    payload = owner._attach_close_review_snapshot(
        db=db,
        payload=payload,
        review_trade_date=latest_completed_trade_date,
        build_if_missing=False,
    )
    return payload.model_copy(
        update={
            "requested_mode": "full",
            "response_mode": "full",
            "full_scan_ready": True,
            "full_scan_in_progress": False,
            "full_scan_updated_at": payload.as_of_date,
        }
    )


def _full_or_pending_response(
    owner: Any,
    *,
    db: Session,
    strategy: str,
    latest_trade_date: str,
    latest_completed_trade_date: str,
    limit: int,
    scan_limit: int,
    include_history: bool,
    full_in_progress: bool,
) -> LowBuyScreenerResponse:
    last_completed = owner._load_latest_materialized_full_result_on_or_before(
        db=db,
        strategy=strategy,
        latest_trade_date=latest_completed_trade_date,
        limit=limit,
        include_history=include_history,
        allow_repair=False,
    )
    if last_completed is not None:
        last_completed = owner._attach_strategy_performance(db=db, payload=last_completed, build_if_missing=False)
        last_completed = owner._attach_close_review_snapshot(
            db=db,
            payload=last_completed,
            review_trade_date=latest_completed_trade_date,
            build_if_missing=False,
        )
        return last_completed.model_copy(
            update={
                "requested_mode": "full",
                "response_mode": "full",
                "full_scan_ready": True,
                "full_scan_in_progress": full_in_progress,
                "full_scan_updated_at": last_completed.as_of_date,
            }
        )
    return _pending_response(
        owner,
        db=db,
        strategy=strategy,
        latest_trade_date=latest_trade_date,
        latest_completed_trade_date=latest_completed_trade_date,
        scan_limit=scan_limit,
        full_scan_in_progress=full_in_progress,
    )


def _pending_response(
    owner: Any,
    *,
    db: Session,
    strategy: str,
    latest_trade_date: str,
    latest_completed_trade_date: str,
    scan_limit: int,
    full_scan_in_progress: bool,
) -> LowBuyScreenerResponse:
    placeholder_performance = owner._load_strategy_performance_snapshot(
        db=db,
        strategy=strategy,
        latest_trade_date=latest_trade_date,
    ) or owner._empty_strategy_performance(
        target_profit_pct=owner._load_stock_profit_target_pct(db),
        lookback_days=PERFORMANCE_LOOKBACK_DAYS,
        note="后台全量深筛仍在补齐，当前先显示等待状态。",
    )
    pending = build_pending_full_response(
        strategy=strategy,
        playbook=owner._get_playbook(strategy),
        latest_trade_date=latest_trade_date,
        requested_scan_limit=owner._resolve_full_scan_limit(scan_limit),
        performance=placeholder_performance,
        full_scan_in_progress=full_scan_in_progress,
    )
    return owner._attach_close_review_snapshot(
        db=db,
        payload=pending,
        review_trade_date=latest_completed_trade_date,
        build_if_missing=False,
    )
