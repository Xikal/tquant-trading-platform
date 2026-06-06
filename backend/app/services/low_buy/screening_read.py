from __future__ import annotations

from typing import Any

from app.services.latest_data_status import expected_low_buy_trade_date, published_low_buy_trade_date, trade_day_gap
from app.services.low_buy_materialization import enqueue_low_buy_materialization
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
    expected_trade_date = expected_low_buy_trade_date(db)
    published_trade_date = published_low_buy_trade_date(db)
    latest_completed_trade_date = published_trade_date or expected_trade_date
    latest_trade_date = latest_completed_trade_date
    stale_days = trade_day_gap(db, published_trade_date, expected_trade_date) if published_trade_date else 0
    if scan_mode == "full":
        cached_full = owner._load_cached_full_result(
            db=db,
            strategy=strategy,
            latest_trade_date=latest_trade_date,
            limit=limit,
            include_history=include_history,
        )
        if cached_full is not None:
            return _full_cached_response(
                owner,
                db=db,
                payload=cached_full,
                latest_completed_trade_date=latest_completed_trade_date,
                expected_trade_date=expected_trade_date,
                stale_days=stale_days,
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
            expected_trade_date=expected_trade_date,
            stale_days=stale_days,
        )

    latest_snapshot = owner._load_cached_full_result(
        db=db,
        strategy=strategy,
        latest_trade_date=latest_trade_date,
        limit=limit,
        include_history=include_history,
    )
    if latest_snapshot is None and not published_trade_date:
        latest_snapshot = owner._load_latest_materialized_full_result_on_or_before(
            db=db,
            strategy=strategy,
            latest_trade_date=expected_trade_date,
            limit=limit,
            include_history=include_history,
        )
        if latest_snapshot is not None:
            latest_completed_trade_date = latest_snapshot.latest_trade_date
            latest_trade_date = latest_completed_trade_date
            stale_days = trade_day_gap(db, latest_completed_trade_date, expected_trade_date)
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
        latest_snapshot = _attach_stale_metadata(
            latest_snapshot,
            expected_trade_date=expected_trade_date,
            stale_days=stale_days,
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

    enqueue_low_buy_materialization(db, reason="screen_latest_missing", commit=True)
    pending = _pending_response(
        owner,
        db=db,
        strategy=strategy,
        latest_trade_date=latest_trade_date,
        latest_completed_trade_date=latest_completed_trade_date,
        scan_limit=scan_limit,
        full_scan_in_progress=full_in_progress,
        expected_trade_date=expected_trade_date,
        stale_days=stale_days,
    )
    return pending.model_copy(update={"requested_mode": scan_mode, "response_mode": "pending"})


def _full_cached_response(
    owner: Any,
    *,
    db: Session,
    payload: LowBuyScreenerResponse,
    latest_completed_trade_date: str,
    expected_trade_date: str,
    stale_days: int,
) -> LowBuyScreenerResponse:
    payload = owner._attach_strategy_performance(db=db, payload=payload, build_if_missing=False)
    payload = owner._attach_close_review_snapshot(
        db=db,
        payload=payload,
        review_trade_date=latest_completed_trade_date,
        build_if_missing=False,
    )
    payload = _attach_stale_metadata(payload, expected_trade_date=expected_trade_date, stale_days=stale_days)
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
    expected_trade_date: str,
    stale_days: int,
) -> LowBuyScreenerResponse:
    last_completed = owner._load_cached_full_result(
        db=db,
        strategy=strategy,
        latest_trade_date=latest_completed_trade_date,
        limit=limit,
        include_history=include_history,
    )
    if last_completed is not None:
        last_completed = owner._attach_strategy_performance(db=db, payload=last_completed, build_if_missing=False)
        last_completed = owner._attach_close_review_snapshot(
            db=db,
            payload=last_completed,
            review_trade_date=latest_completed_trade_date,
            build_if_missing=False,
        )
        last_completed = _attach_stale_metadata(
            last_completed,
            expected_trade_date=expected_trade_date,
            stale_days=stale_days,
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
    if not latest_completed_trade_date or latest_completed_trade_date == expected_trade_date:
        last_completed = owner._load_latest_materialized_full_result_on_or_before(
            db=db,
            strategy=strategy,
            latest_trade_date=expected_trade_date,
            limit=limit,
            include_history=include_history,
        )
        if last_completed is not None:
            fallback_trade_date = last_completed.latest_trade_date
            fallback_stale_days = trade_day_gap(db, fallback_trade_date, expected_trade_date)
            last_completed = owner._attach_strategy_performance(db=db, payload=last_completed, build_if_missing=False)
            last_completed = owner._attach_close_review_snapshot(
                db=db,
                payload=last_completed,
                review_trade_date=fallback_trade_date,
                build_if_missing=False,
            )
            last_completed = _attach_stale_metadata(
                last_completed,
                expected_trade_date=expected_trade_date,
                stale_days=fallback_stale_days,
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
    enqueue_low_buy_materialization(db, reason="screen_full_latest_missing", commit=True)
    return _pending_response(
        owner,
        db=db,
        strategy=strategy,
        latest_trade_date=latest_trade_date,
        latest_completed_trade_date=latest_completed_trade_date,
        scan_limit=scan_limit,
        full_scan_in_progress=full_in_progress,
        expected_trade_date=expected_trade_date,
        stale_days=stale_days,
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
    expected_trade_date: str,
    stale_days: int,
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
    pending = owner._attach_close_review_snapshot(
        db=db,
        payload=pending,
        review_trade_date=latest_completed_trade_date,
        build_if_missing=False,
    )
    return _attach_stale_metadata(pending, expected_trade_date=expected_trade_date, stale_days=stale_days)


def _attach_stale_metadata(
    payload: LowBuyScreenerResponse,
    *,
    expected_trade_date: str,
    stale_days: int,
) -> LowBuyScreenerResponse:
    if stale_days <= 0:
        return payload.model_copy(update={"stale": False, "stale_reason": ""})
    reason = (
        f"当前选股宝典停留在 {payload.latest_trade_date}，"
        f"距最新交易日 {expected_trade_date} 已落后 {stale_days} 个交易日，"
        "仅供复盘，不作为今日观察。"
    )
    warning = " ".join(item for item in (payload.snapshot_warning, reason) if item).strip()
    return payload.model_copy(update={"snapshot_warning": warning, "stale": True, "stale_reason": reason})
