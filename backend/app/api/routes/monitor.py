from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.timezone import beijing_now_string
from app.models.entities import User
from app.models.schema_defs.monitor import MonitorSnapshotResponse
from app.services.monitor_snapshot_cache import (
    enqueue_monitor_snapshot_refresh,
    fallback_watchlist_signals,
    list_user_watchlist_rows,
    read_monitor_snapshot_cache,
    rows_signature,
)
from app.services.user_sector_preferences import UserSectorPreferenceService, filter_monitor_snapshot_payload

router = APIRouter(prefix="/monitor", dependencies=[Depends(get_current_user)])


@router.get("/snapshot", response_model=MonitorSnapshotResponse)
def monitor_snapshot(
    priority_limit: int = Query(default=12, ge=1, le=30),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MonitorSnapshotResponse:
    """Return the desktop monitor payload in one request.

    This keeps the UI on materialized/read paths and avoids separate polling for
    watchlist signals and the all-strategy priority board.
    """

    rows = list_user_watchlist_rows(db, current_user.id)
    excluded = _safe_excluded_sectors(db, current_user.id)
    signature = _rows_signature(rows, excluded)
    cached = read_monitor_snapshot_cache(
        db,
        user_id=current_user.id,
        priority_limit=priority_limit,
        signature=signature,
    )
    if cached is not None:
        if cached.needs_refresh:
            enqueue_monitor_snapshot_refresh(
                db,
                user_id=current_user.id,
                priority_limit=priority_limit,
            )
        return MonitorSnapshotResponse(**filter_monitor_snapshot_payload(cached.payload, excluded))

    # Cold start path: return a small, explicit fallback immediately and let the
    # runtime worker perform expensive analysis/priority refresh.  The Web
    # process no longer starts in-process threads from user requests.
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
        priority_board=_empty_priority_board(
            warning="监控榜单刷新任务已排队，稍后会自动更新。",
        ),
        sector_etf_t0=_empty_sector_etf_t0(),
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


def _empty_sector_etf_t0() -> dict[str, Any]:
    return {
        "updated_at": beijing_now_string(),
        "market_state": "neutral",
        "market_state_text": "数据刷新中",
        "total": 0,
        "opportunities": [],
        "notes": ["监控刷新任务已排队，ETF 做T替代稍后自动更新。"],
    }
