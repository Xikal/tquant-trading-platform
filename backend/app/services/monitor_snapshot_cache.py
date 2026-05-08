from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.timezone import beijing_now_string
from app.models.entities import SystemSetting, UserWatchlist
from app.models.schema_defs.phase4 import RuntimeTaskCreate
from app.services.low_buy_screener import LowBuyScreenerService
from app.services.sector_etf_t0 import SectorEtfT0Service
from app.services.tasks import RuntimeTaskQueue
from app.services.user_sector_preferences import (
    UserSectorPreferenceService,
    filter_monitor_snapshot_payload,
)
from app.services.watchlist_signal_service import WatchlistSignalService

_MONITOR_CACHE_TTL_SECONDS = 20.0
_MONITOR_STALE_TTL_SECONDS = 600.0
_CACHE_KEY_PREFIX = "monitor_cache"
_TASK_TYPE = "monitor_snapshot_refresh"

watchlist_signal_service = WatchlistSignalService()
low_buy_screener = LowBuyScreenerService()
sector_etf_t0_service = SectorEtfT0Service(low_buy=low_buy_screener)


@dataclass(frozen=True)
class MonitorSnapshotCacheHit:
    payload: dict[str, Any]
    needs_refresh: bool


def list_user_watchlist_rows(db: Session, user_id: int) -> list[UserWatchlist]:
    return (
        db.execute(
            select(UserWatchlist)
            .where(UserWatchlist.user_id == user_id)
            .order_by(UserWatchlist.id.desc())
        )
        .scalars()
        .all()
    )


def rows_signature(rows: list[UserWatchlist], excluded_sectors: set[str] | None = None) -> list[list[Any]]:
    """Build a small stable signature so stale cache is not reused after edits."""

    signature = [
        [
            str(getattr(row, "symbol", "") or ""),
            str(getattr(row, "name", "") or ""),
            int(getattr(row, "base_position", 0) or 0),
            int(getattr(row, "available_position", 0) or 0),
            float(getattr(row, "cost_basis", 0.0) or 0.0),
            str(getattr(row, "memo", "") or ""),
        ]
        for row in rows
    ]
    if excluded_sectors:
        signature.append(["__sector_exclusions__", *sorted(excluded_sectors)])
    return signature


def read_monitor_snapshot_cache(
    db: Session,
    *,
    user_id: int,
    priority_limit: int,
    signature: list[list[Any]],
) -> MonitorSnapshotCacheHit | None:
    row = db.execute(
        select(SystemSetting).where(SystemSetting.key == _cache_key(user_id, priority_limit))
    ).scalar_one_or_none()
    if row is None:
        return None
    value = _json_dict(row.value)
    if value.get("signature") != signature:
        return None
    now = time.time()
    stale_at = _float_value(value.get("stale_at"))
    if stale_at <= now:
        return None
    payload = value.get("payload")
    if not isinstance(payload, dict):
        return None
    expires_at = _float_value(value.get("expires_at"))
    return MonitorSnapshotCacheHit(payload=payload, needs_refresh=expires_at <= now)


def enqueue_monitor_snapshot_refresh(
    db: Session,
    *,
    user_id: int,
    priority_limit: int,
) -> None:
    RuntimeTaskQueue(db).enqueue(
        RuntimeTaskCreate(
            task_type=_TASK_TYPE,
            payload={"user_id": user_id, "priority_limit": priority_limit},
            priority=60,
            idempotency_key=f"{_TASK_TYPE}:{user_id}:{priority_limit}",
            max_attempts=2,
        )
    )


def fallback_watchlist_signals(rows: list[UserWatchlist], *, reason: str) -> list[dict[str, Any]]:
    return watchlist_signal_service.fallback_signals_for_rows(rows, reason=reason)


def build_and_store_monitor_snapshot(
    db: Session,
    *,
    user_id: int,
    priority_limit: int,
) -> dict[str, Any]:
    rows = list_user_watchlist_rows(db, user_id)
    excluded = UserSectorPreferenceService(db).get_excluded_sector_set(user_id)
    signature = rows_signature(rows, excluded)
    signals = watchlist_signal_service.build_live_signals(db, rows)
    board_response = low_buy_screener.priority_board(db=db, limit=priority_limit)
    board = board_response.model_dump()
    sector_etf_t0 = sector_etf_t0_service.build_from_priority_board(
        board_response,
        limit=min(max(priority_limit, 1), 8),
    ).model_dump()
    payload = {
        "updated_at": beijing_now_string(),
        "watchlist_signals": signals,
        "priority_board": board,
        "sector_etf_t0": sector_etf_t0,
    }
    payload = filter_monitor_snapshot_payload(payload, excluded)
    _write_monitor_snapshot_cache(
        db,
        user_id=user_id,
        priority_limit=priority_limit,
        signature=signature,
        payload=payload,
    )
    return {
        "ok": True,
        "user_id": user_id,
        "priority_limit": priority_limit,
        "watchlist_count": len(signals),
        "priority_count": int(board.get("total_candidates") or len(board.get("items") or [])),
    }


def _write_monitor_snapshot_cache(
    db: Session,
    *,
    user_id: int,
    priority_limit: int,
    signature: list[list[Any]],
    payload: dict[str, Any],
) -> None:
    now = time.time()
    value = {
        "signature": signature,
        "expires_at": now + _MONITOR_CACHE_TTL_SECONDS,
        "stale_at": now + _MONITOR_STALE_TTL_SECONDS,
        "payload": payload,
    }
    key = _cache_key(user_id, priority_limit)
    row = db.execute(select(SystemSetting).where(SystemSetting.key == key)).scalar_one_or_none()
    if row is None:
        row = SystemSetting(key=key, value=_json_dumps(value))
        db.add(row)
    else:
        row.value = _json_dumps(value)


def _cache_key(user_id: int, priority_limit: int) -> str:
    return f"{_CACHE_KEY_PREFIX}:{user_id}:{priority_limit}"


def _json_dumps(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _json_dict(raw: str) -> dict[str, Any]:
    try:
        value = json.loads(raw or "{}")
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _float_value(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
