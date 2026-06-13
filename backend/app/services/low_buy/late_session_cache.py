from __future__ import annotations

import hashlib
import time

from app.models.schema_defs.late_session_board import LateSessionBoardResponse
from app.services.shared.distributed_cache import get_json_cache, set_json_cache


def late_session_cache_key(
    *,
    trade_date: str,
    slot: str,
    strategy_variant: str,
    source_epoch: str,
    user_filter_hash: str = "global",
) -> str:
    return ":".join(
        [
            "late_session_board",
            str(trade_date or "unknown"),
            str(slot or "latest"),
            str(strategy_variant or "baseline"),
            str(source_epoch or "0"),
            str(user_filter_hash or "global"),
        ]
    )


def late_session_ttl_seconds(slot: str) -> int:
    normalized = str(slot or "latest")
    if normalized == "preview_1450":
        return 10 * 60
    if normalized == "snapshot_1455":
        return 6 * 60 * 60
    if normalized == "final_1457":
        return 7 * 24 * 60 * 60
    return 10 * 60


def user_filter_hash(excluded_sectors: list[str] | tuple[str, ...] | set[str] | frozenset[str]) -> str:
    cleaned = "|".join(sorted(str(item).strip() for item in excluded_sectors if str(item).strip()))
    if not cleaned:
        return "global"
    return "u:" + hashlib.sha1(cleaned.encode("utf-8")).hexdigest()[:12]


def store_late_session_board_snapshot(
    cache: dict[str, tuple[float, str]],
    key: str,
    payload: LateSessionBoardResponse,
    *,
    ttl_seconds: int | float,
) -> None:
    cache[key] = (time.monotonic() + max(float(ttl_seconds), 1.0), payload.model_dump_json())


def load_late_session_board_snapshot(cache: dict[str, tuple[float, str]], key: str) -> LateSessionBoardResponse | None:
    cached = cache.get(key)
    if cached is None:
        return None
    expires_at, payload_json = cached
    if expires_at <= time.monotonic():
        cache.pop(key, None)
        return None
    return LateSessionBoardResponse.model_validate_json(payload_json)


def store_distributed_late_session_board_snapshot(
    key: str,
    payload: LateSessionBoardResponse,
    *,
    ttl_seconds: int | float,
) -> bool:
    return set_json_cache(key, payload.model_dump(mode="json"), ttl_seconds=ttl_seconds)


def load_distributed_late_session_board_snapshot(key: str) -> LateSessionBoardResponse | None:
    payload = get_json_cache(key)
    if not isinstance(payload, dict):
        return None
    try:
        return LateSessionBoardResponse.model_validate(payload)
    except Exception:
        return None
