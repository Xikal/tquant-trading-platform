from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.core.timezone import beijing_now_string
from app.models.entities import User
from app.models.schema_defs.monitor import MonitorSnapshotResponse
from app.services.latest_data_status import expected_low_buy_trade_date
from app.services.monitor_snapshot_cache import (
    enqueue_monitor_snapshot_refresh,
    fallback_watchlist_signals,
    list_user_watchlist_rows,
    read_monitor_snapshot_cache,
    rows_signature,
)
from app.services.performance.read_model_metrics import record_read_model_cache_hit, record_read_model_cache_miss
from app.services.user_sector_preferences import UserSectorPreferenceService, filter_monitor_snapshot_payload

logger = logging.getLogger(__name__)


def build_monitor_snapshot(
    db: Session,
    *,
    current_user: User,
    priority_limit: int,
) -> MonitorSnapshotResponse:
    """Read the monitor snapshot without doing heavy compute in the request path."""

    rows = list_user_watchlist_rows(db, current_user.id)
    excluded = _safe_excluded_sectors(db, current_user.id)
    signature = _rows_signature(rows, excluded)
    required_trade_date = _safe_expected_trade_date(db)
    cached = read_monitor_snapshot_cache(
        db,
        user_id=current_user.id,
        priority_limit=priority_limit,
        signature=signature,
        required_trade_date=required_trade_date,
    )
    if cached is not None:
        record_read_model_cache_hit("monitor_workspace")
        payload = filter_monitor_snapshot_payload(cached.payload, excluded)
        should_probe_priority_board = cached.needs_refresh or _priority_board_needs_read_model_probe(payload)
        if cached.needs_refresh:
            enqueue_monitor_snapshot_refresh(
                db,
                user_id=current_user.id,
                priority_limit=priority_limit,
            )
        if should_probe_priority_board:
            payload = _with_fresher_priority_board(
                payload,
                db,
                priority_limit=priority_limit,
                excluded_sectors=excluded,
            )
        return MonitorSnapshotResponse(**payload)

    record_read_model_cache_miss("monitor_workspace")
    enqueue_monitor_snapshot_refresh(
        db,
        user_id=current_user.id,
        priority_limit=priority_limit,
    )
    return MonitorSnapshotResponse(
        updated_at=beijing_now_string(),
        watchlist_signals=fallback_watchlist_signals(
            rows,
            reason="监控数据刷新任务已排队，先按观望处理。",
        ),
        priority_board=_fallback_priority_board_from_read_model(
            db,
            priority_limit=priority_limit,
        )
        or _empty_priority_board(
            warning="监控榜单刷新任务已排队，稍后会自动更新。",
        ),
        sector_etf_t0=_empty_sector_etf_t0(),
    )


def _fallback_priority_board_from_read_model(db: Session, *, priority_limit: int) -> dict[str, Any] | None:
    try:
        from app.services.low_buy_screener import LowBuyScreenerService
        from app.services.read_models.live_quote_overlay import apply_priority_board_live_overlay

        board = LowBuyScreenerService().priority_board(
            db=db,
            limit=priority_limit,
            refresh_mode="cache",
            strategy_variant="baseline",
        )
        board = apply_priority_board_live_overlay(board)
        payload = board.model_dump(mode="json")
        if payload.get("items"):
            return payload
    except Exception as exc:  # pragma: no cover - defensive fallback path
        logger.warning(
            "monitor priority board fallback unavailable priority_limit=%s",
            priority_limit,
            exc_info=(type(exc), exc, exc.__traceback__),
        )
    return None


def _with_fresher_priority_board(
    payload: dict[str, Any],
    db: Session,
    *,
    priority_limit: int,
    excluded_sectors: set[str],
) -> dict[str, Any]:
    fallback = _fallback_priority_board_from_read_model(db, priority_limit=priority_limit)
    if not fallback:
        return payload
    fallback = filter_monitor_snapshot_payload({"priority_board": fallback}, excluded_sectors).get("priority_board", fallback)
    current = payload.get("priority_board")
    if not isinstance(current, dict) or _should_replace_priority_board(current, fallback):
        return {**payload, "priority_board": fallback}
    return payload


def _should_replace_priority_board(current: dict[str, Any], fallback: dict[str, Any]) -> bool:
    if not fallback.get("items"):
        return False
    current_trade_date = _date_text(current.get("latest_trade_date") or current.get("latest_available_trade_date"))
    fallback_trade_date = _date_text(fallback.get("latest_trade_date") or fallback.get("latest_available_trade_date"))
    if fallback_trade_date and fallback_trade_date > current_trade_date:
        return True
    if fallback_trade_date and fallback_trade_date < current_trade_date:
        return False

    current_updated = _date_time_text(current.get("updated_at") or current.get("as_of_date"))
    fallback_updated = _date_time_text(fallback.get("updated_at") or fallback.get("as_of_date"))
    if fallback_updated and fallback_updated > current_updated:
        return True

    if _is_stale_board(current) and not _is_stale_board(fallback):
        return True

    if current_updated == fallback_updated and _board_signature(current) != _board_signature(fallback):
        return True
    return False


def _date_text(value: Any) -> str:
    return str(value or "")[:10]


def _date_time_text(value: Any) -> str:
    return str(value or "")


def _is_stale_board(board: dict[str, Any]) -> bool:
    quality = str(board.get("data_quality") or "").lower()
    warning = str(board.get("snapshot_warning") or board.get("stale_reason") or "")
    return bool(board.get("stale")) or quality == "stale" or "刷新" in warning


def _priority_board_needs_read_model_probe(payload: dict[str, Any]) -> bool:
    board = payload.get("priority_board")
    if not isinstance(board, dict):
        return False
    read_path = str(board.get("read_path") or "")
    return _is_stale_board(board) or read_path == "priority_board_latest_successful_snapshot"


def _board_signature(board: dict[str, Any]) -> tuple[Any, ...]:
    items = board.get("items")
    symbols: tuple[str, ...] = ()
    states: tuple[str, ...] = ()
    if isinstance(items, list):
        symbols = tuple(str(item.get("symbol") or "") for item in items if isinstance(item, dict))
        states = tuple(str(item.get("buy_signal_state") or item.get("simple_bucket") or "") for item in items if isinstance(item, dict))
    return (
        board.get("total_candidates"),
        board.get("immediate_count"),
        board.get("focus_count"),
        board.get("track_count"),
        symbols,
        states,
    )
def _empty_priority_board(*, warning: str) -> dict[str, Any]:
    return {
        "as_of_date": beijing_now_string(),
        "latest_trade_date": "",
        "latest_available_trade_date": "",
        "snapshot_warning": warning,
        "updated_at": beijing_now_string(),
        "total_candidates": 0,
        "immediate_count": 0,
        "focus_count": 0,
        "track_count": 0,
        "market_state": "neutral",
        "market_state_text": "数据刷新中",
        "market_state_category": "low_volume_wait",
        "market_state_category_text": "等待数据",
        "data_quality": "stale",
        "data_quality_text": "后台刷新中",
        "data_quality_tags": ["后台刷新中"],
        "directional_bias": "neutral",
        "directional_bias_text": "观望",
        "market_bonus": 0.0,
        "market_state_strength": 0.0,
        "regime_confidence": 0.0,
        "state_persistence_days": 1,
        "transition_risk": 0.0,
        "breadth_ready": False,
        "emotion_ready": False,
        "stock_up_ratio": 0.0,
        "stock_median_change": 0.0,
        "style_divergence": 0.0,
        "hot_turnover": 0.0,
        "hot_overlap_ratio": 0.0,
        "limit_down_count": None,
        "limit_up_count": 0,
        "board_height": 0,
        "previous_board_height": 0,
        "promotion_ratio": 0.0,
        "broken_board_ratio": 0.0,
        "promotion_break_gap": 0.0,
        "promotion_break_pressure": 0.0,
        "high_flyer_retreat_ratio": 0.0,
        "high_flyer_gap_speed": 0.0,
        "distribution_pressure": 0.0,
        "hot_industries": [],
        "hot_industry_source": "",
        "hot_industry_source_text": "",
        "mainline_lifecycle_state": "",
        "mainline_lifecycle_text": "",
        "missing_strategies": [],
        "stale_strategies": [],
        "family_sections": [],
        "simple_buckets": [],
        "items": [],
    }


def _empty_sector_etf_t0() -> dict[str, Any]:
    return {
        "updated_at": beijing_now_string(),
        "market_state": "neutral",
        "market_state_text": "数据刷新中",
        "total": 0,
        "opportunities": [],
        "notes": ["监控刷新任务已排队，ETF 做T替代稍后自动更新。"],
    }


def _safe_expected_trade_date(db: Session) -> str:
    try:
        return expected_low_buy_trade_date(db)
    except Exception:
        return ""


def _safe_excluded_sectors(db: Session, user_id: int) -> set[str]:
    try:
        return UserSectorPreferenceService(db).get_excluded_sector_set(user_id)
    except Exception:
        return set()


def _rows_signature(rows: list[Any], excluded: set[str]) -> Any:
    try:
        return rows_signature(rows, excluded)
    except TypeError:
        return rows_signature(rows)
