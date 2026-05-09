from __future__ import annotations

import time

from app.services.low_buy.cache_helpers import (
    get_daily_history_cache,
    get_history_cache,
    get_model_cache,
    set_daily_history_cache,
    set_model_cache,
)
from app.services.low_buy.shared import LowBuyHistoryResponse, pd


class LowBuyHistoryCacheMixin:
    @classmethod
    def _get_screen_cache(cls, cache_key: str):
        return get_model_cache(cls._screen_cache, cls._cache_lock, cache_key)

    @classmethod
    def _set_screen_cache(cls, cache_key: str, payload, ttl: float | None = None) -> None:
        set_model_cache(cls._screen_cache, cls._cache_lock, cache_key, payload, ttl or cls._screen_cache_ttl)

    @classmethod
    def _get_history_cache(cls, cache_key: str):
        return get_history_cache(cls._screen_cache, cls._cache_lock, cache_key)

    @classmethod
    def _set_history_cache(cls, cache_key: str, payload: LowBuyHistoryResponse) -> None:
        set_model_cache(cls._screen_cache, cls._cache_lock, cache_key, payload, cls._screen_cache_ttl)

    @classmethod
    def _get_daily_history_cache(cls, cache_key: str):
        return get_daily_history_cache(cls._daily_history_cache, cls._cache_lock, cache_key)

    @classmethod
    def _set_daily_history_cache(cls, cache_key: str, payload: pd.DataFrame | None) -> None:
        set_daily_history_cache(cls._daily_history_cache, cls._cache_lock, cache_key, payload, cls._daily_history_cache_ttl)

    @classmethod
    def _get_spot_quote_cache(cls):
        now = time.monotonic()
        with cls._cache_lock:
            cached = cls._spot_quote_cache
            if cached is None:
                return None
            expires_at, payload = cached
            if expires_at <= now:
                cls._spot_quote_cache = None
                return None
            return dict(payload)

    @classmethod
    def _set_spot_quote_cache(cls, payload) -> None:
        with cls._cache_lock:
            cls._spot_quote_cache = (time.monotonic() + cls._spot_quote_cache_ttl, dict(payload))
