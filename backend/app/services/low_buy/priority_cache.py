from __future__ import annotations

from copy import deepcopy
import time

from app.models.schemas import LowBuyPriorityBoardResponse
from app.services.low_buy.priority_types import PriorityBaseSnapshot
from app.services.performance.read_model_metrics import (
    record_read_model_cache_hit,
    record_read_model_cache_miss,
    record_read_model_cache_stale,
    record_read_model_cache_write,
)
from app.services.shared.distributed_cache import get_text_cache, set_text_cache

PRIORITY_RESPONSE_CACHE_VERSION = "priority-response-v1"
PRIORITY_BOARD_CACHE_EPOCH_FALLBACK = "0"
PRIORITY_BOARD_CACHE_EPOCH_TTL_SECONDS = 7 * 24 * 60 * 60


def get_priority_base_cache(service, cache_key: str) -> PriorityBaseSnapshot | None:
    now = time.monotonic()
    with service._cache_lock:
        cached = service._priority_base_cache.get(cache_key)
        if cached is None:
            return None
        expires_at, payload = cached
        if expires_at <= now:
            service._priority_base_cache.pop(cache_key, None)
            return None
        return deepcopy(payload)


def set_priority_base_cache(service, cache_key: str, payload: PriorityBaseSnapshot) -> None:
    with service._cache_lock:
        service._priority_base_cache[cache_key] = (
            time.monotonic() + service._priority_base_cache_ttl,
            deepcopy(payload),
        )


def get_priority_response_cache(
    service,
    cache_key: str,
    *,
    allow_stale: bool = False,
) -> LowBuyPriorityBoardResponse | None:
    now = time.monotonic()
    stale_local: LowBuyPriorityBoardResponse | None = None
    cache_key = _versioned_local_key(cache_key)
    with service._cache_lock:
        cached = service._priority_response_cache.get(cache_key)
        if cached is not None:
            expires_at, payload = cached
            parsed = LowBuyPriorityBoardResponse.model_validate_json(payload) if isinstance(payload, str) else deepcopy(payload)
            if expires_at > now:
                record_read_model_cache_hit("priority_board")
                return parsed
            stale_local = parsed
            record_read_model_cache_stale("priority_board")
            if not allow_stale:
                service._priority_response_cache.pop(cache_key, None)
    distributed = get_text_cache(_distributed_key(cache_key))
    if distributed:
        payload = LowBuyPriorityBoardResponse.model_validate_json(distributed)
        with service._cache_lock:
            service._priority_response_cache[cache_key] = (
                time.monotonic() + service._priority_response_cache_ttl,
                distributed,
            )
        record_read_model_cache_hit("priority_board")
        return payload
    record_read_model_cache_miss("priority_board")
    return stale_local if allow_stale else None


def set_priority_response_cache(service, cache_key: str, payload: LowBuyPriorityBoardResponse) -> None:
    cache_key = _versioned_local_key(cache_key)
    serialized = payload.model_dump_json()
    set_text_cache(_distributed_key(cache_key), serialized, service._priority_response_cache_ttl)
    record_read_model_cache_write("priority_board")
    with service._cache_lock:
        service._priority_response_cache[cache_key] = (
            time.monotonic() + service._priority_response_cache_ttl,
            serialized,
        )


def priority_board_cache_epoch(trade_date: str) -> str:
    value = get_text_cache(_cache_epoch_key(trade_date), fail_open=True)
    return str(value or PRIORITY_BOARD_CACHE_EPOCH_FALLBACK)


def bump_priority_board_cache_epoch(trade_date: str, *, reason: str = "priority_board_cache_invalidation") -> dict[str, object]:
    clean_trade_date = str(trade_date or "").strip()
    if not clean_trade_date:
        return {
            "ok": False,
            "trade_date": "",
            "cache_epoch": "",
            "stored": False,
            "reason": "missing_trade_date",
        }
    epoch = str(time.time_ns())
    stored = set_text_cache(
        _cache_epoch_key(clean_trade_date),
        epoch,
        PRIORITY_BOARD_CACHE_EPOCH_TTL_SECONDS,
        fail_open=True,
    )
    return {
        "ok": bool(stored),
        "trade_date": clean_trade_date,
        "cache_epoch": epoch,
        "stored": bool(stored),
        "reason": reason,
    }


def _distributed_key(cache_key: str) -> str:
    return f"tquant:low_buy:priority_response:{cache_key}"


def _versioned_local_key(cache_key: str) -> str:
    return f"{PRIORITY_RESPONSE_CACHE_VERSION}:{cache_key}"


def _cache_epoch_key(trade_date: str) -> str:
    return f"tquant:low_buy:priority_board_epoch:{str(trade_date or 'unknown').strip() or 'unknown'}"
