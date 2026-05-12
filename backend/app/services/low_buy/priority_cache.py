from __future__ import annotations

from copy import deepcopy
import time

from app.models.schemas import LowBuyPriorityBoardResponse
from app.services.low_buy.priority_types import PriorityBaseSnapshot
from app.services.shared.distributed_cache import get_text_cache, set_text_cache


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


def get_priority_response_cache(service, cache_key: str) -> LowBuyPriorityBoardResponse | None:
    now = time.monotonic()
    with service._cache_lock:
        cached = service._priority_response_cache.get(cache_key)
        if cached is None:
            return None
        expires_at, payload = cached
        if expires_at <= now:
            service._priority_response_cache.pop(cache_key, None)
            return None
        if isinstance(payload, str):
            return LowBuyPriorityBoardResponse.model_validate_json(payload)
        return deepcopy(payload)
    distributed = get_text_cache(_distributed_key(cache_key))
    if distributed:
        payload = LowBuyPriorityBoardResponse.model_validate_json(distributed)
        with service._cache_lock:
            service._priority_response_cache[cache_key] = (
                time.monotonic() + service._priority_response_cache_ttl,
                distributed,
            )
        return payload
    return None


def set_priority_response_cache(service, cache_key: str, payload: LowBuyPriorityBoardResponse) -> None:
    serialized = payload.model_dump_json()
    set_text_cache(_distributed_key(cache_key), serialized, service._priority_response_cache_ttl)
    with service._cache_lock:
        service._priority_response_cache[cache_key] = (
            time.monotonic() + service._priority_response_cache_ttl,
            serialized,
        )


def _distributed_key(cache_key: str) -> str:
    return f"tquant:low_buy:priority_response:{cache_key}"
