from __future__ import annotations

import time
from typing import Any

import pandas as pd

from app.services.low_buy.shared import LowBuyHistoryResponse


def get_model_cache(cache: dict[str, tuple[float, Any]], lock, cache_key: str):
    now = time.monotonic()
    with lock:
        cached = cache.get(cache_key)
        if cached is None:
            return None
        expires_at, payload = cached
        if expires_at <= now:
            cache.pop(cache_key, None)
            return None
        return _restore_model_payload(payload)


def set_model_cache(cache: dict[str, tuple[float, Any]], lock, cache_key: str, payload: Any, ttl: float) -> None:
    with lock:
        cache[cache_key] = (time.monotonic() + ttl, _dump_model_payload(payload))


def get_history_cache(cache: dict[str, tuple[float, Any]], lock, cache_key: str):
    payload = get_model_cache(cache, lock, cache_key)
    if isinstance(payload, LowBuyHistoryResponse):
        return payload
    return None


def get_daily_history_cache(cache: dict[str, tuple[float, pd.DataFrame | None]], lock, cache_key: str):
    now = time.monotonic()
    with lock:
        cached = cache.get(cache_key)
        if cached is None:
            return None
        expires_at, payload = cached
        if expires_at <= now:
            cache.pop(cache_key, None)
            return None
        return payload


def set_daily_history_cache(
    cache: dict[str, tuple[float, pd.DataFrame | None]],
    lock,
    cache_key: str,
    payload: pd.DataFrame | None,
    ttl: float,
) -> None:
    with lock:
        cache[cache_key] = (time.monotonic() + ttl, payload.copy(deep=True) if payload is not None else None)


def get_spot_quote_cache(cached_entry, lock):
    now = time.monotonic()
    with lock:
        if cached_entry is None:
            return None
        expires_at, payload = cached_entry
        if expires_at <= now:
            return None
        return dict(payload)


def _dump_model_payload(payload: Any) -> Any:
    if hasattr(payload, "model_dump_json"):
        return {
            "__pydantic_model__": payload.__class__,
            "payload_json": payload.model_dump_json(),
        }
    if hasattr(payload, "model_copy"):
        return payload.model_copy(deep=True)
    return payload


def _restore_model_payload(payload: Any) -> Any:
    if isinstance(payload, dict) and "__pydantic_model__" in payload:
        model_cls = payload.get("__pydantic_model__")
        payload_json = payload.get("payload_json", "")
        if hasattr(model_cls, "model_validate_json"):
            return model_cls.model_validate_json(payload_json)
    if hasattr(payload, "model_copy"):
        return payload.model_copy(deep=True)
    return payload
