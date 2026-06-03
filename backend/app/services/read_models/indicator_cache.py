from __future__ import annotations

import hashlib
import json
import threading
import time
from collections import OrderedDict, defaultdict
from collections.abc import Callable, Sequence
from typing import TypeVar

from app.core.config import get_settings
from app.services.finance.rust_math import rolling_mean

T = TypeVar("T")
INDICATOR_CACHE_VERSION = "indicator-cache-v1"
_MAX_SIZE = 512
_LOCK = threading.RLock()
_CACHE: OrderedDict[tuple[str, str, str, str, str, str], tuple[float, object]] = OrderedDict()
_METRICS: dict[str, defaultdict[str, int]] = {
    "hits": defaultdict(int),
    "misses": defaultdict(int),
}


def get_or_compute_indicator(
    *,
    indicator: str,
    symbol: str,
    trade_date: str,
    params_hash: str,
    indicator_version: str = INDICATOR_CACHE_VERSION,
    loader: Callable[[], T],
) -> T:
    settings = get_settings()
    if not settings.derived_indicator_cache_enabled:
        return loader()
    ttl = max(int(settings.derived_indicator_cache_ttl_seconds or 0), 0)
    if ttl <= 0:
        return loader()
    key = _cache_key(
        indicator=indicator,
        symbol=symbol,
        trade_date=trade_date,
        params_hash=params_hash,
        indicator_version=indicator_version,
    )
    now = time.monotonic()
    with _LOCK:
        cached = _CACHE.get(key)
        if cached is not None:
            expires_at, payload = cached
            if expires_at > now:
                _METRICS["hits"][indicator] += 1
                _CACHE.move_to_end(key)
                return payload  # type: ignore[return-value]
            _CACHE.pop(key, None)
        _METRICS["misses"][indicator] += 1
    value = loader()
    with _LOCK:
        _CACHE[key] = (time.monotonic() + ttl, value)
        _CACHE.move_to_end(key)
        while len(_CACHE) > _MAX_SIZE:
            _CACHE.popitem(last=False)
    return value


def cached_rolling_mean_latest(
    *,
    symbol: str,
    trade_date: str,
    values: Sequence[float],
    window: int,
    indicator_version: str = INDICATOR_CACHE_VERSION,
) -> float:
    cleaned = [float(value) for value in values]
    params_hash = hash_indicator_params({"window": int(window), "values": cleaned})

    def loader() -> float:
        if not cleaned:
            return 0.0
        if len(cleaned) < int(window):
            return sum(cleaned) / len(cleaned)
        series = rolling_mean(cleaned, int(window))
        latest = series[-1] if series else None
        if latest is None:
            return sum(cleaned[-int(window) :]) / int(window)
        return float(latest)

    return float(
        get_or_compute_indicator(
            indicator="rolling_mean",
            symbol=symbol,
            trade_date=trade_date,
            params_hash=params_hash,
            indicator_version=indicator_version,
            loader=loader,
        )
    )


def hash_indicator_params(payload: object) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def indicator_cache_metrics_snapshot() -> dict[str, dict[str, float]]:
    with _LOCK:
        size: defaultdict[str, int] = defaultdict(int)
        for key in _CACHE:
            size[key[0]] += 1
        return {
            "hits": {key: float(value) for key, value in _METRICS["hits"].items()},
            "misses": {key: float(value) for key, value in _METRICS["misses"].items()},
            "size": {key: float(value) for key, value in size.items()},
        }


def reset_indicator_cache() -> None:
    with _LOCK:
        _CACHE.clear()
        for values in _METRICS.values():
            values.clear()


def _cache_key(
    *,
    indicator: str,
    symbol: str,
    trade_date: str,
    params_hash: str,
    indicator_version: str,
) -> tuple[str, str, str, str, str, str]:
    return (
        str(indicator or "unknown"),
        str(symbol or ""),
        str(trade_date or ""),
        str(params_hash or ""),
        str(indicator_version or INDICATOR_CACHE_VERSION),
        "indicator|symbol|trade_date|params_hash|indicator_version",
    )

