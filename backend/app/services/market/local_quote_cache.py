from __future__ import annotations

import threading
import time
from typing import Any

from app.models.schemas import QuoteSnapshot
from app.services.shared.distributed_cache import get_json_cache, set_json_cache, set_many_json_cache

LOCAL_QUOTE_TTL_SECONDS = 45
LOCAL_QUOTE_FRESH_AGE_SECONDS = 15
_LOCAL_QUOTE_TTL_SECONDS = LOCAL_QUOTE_TTL_SECONDS
_FRESH_LOCAL_AGE_SECONDS = LOCAL_QUOTE_FRESH_AGE_SECONDS
_LOCK = threading.RLock()
_METRICS = {
    "reads": 0,
    "hits": 0,
    "writes": 0,
    "fresh_hits": 0,
    "stale_hits": 0,
    "estimated_hits": 0,
    "misses": 0,
}


def read_local_quote_snapshot(symbol: str) -> QuoteSnapshot | None:
    _increment("reads")
    payload = get_json_cache(_cache_key(symbol))
    if payload is None:
        _increment("misses")
        return None
    snapshot, cached_at = _parse_payload(payload)
    if snapshot is None:
        _increment("misses")
        return None
    age_seconds = max(time.time() - cached_at, 0.0) if cached_at else _LOCAL_QUOTE_TTL_SECONDS + 1
    if age_seconds <= _FRESH_LOCAL_AGE_SECONDS:
        _increment("hits")
        _increment("fresh_hits")
        return snapshot.model_copy(
            update={
                "data_source": snapshot.data_source or "local_quote_cache",
                "source_quality": snapshot.source_quality or snapshot.data_quality or "fresh",
                "data_quality": snapshot.data_quality or "fresh",
                "data_quality_message": snapshot.data_quality_message or "来自本地行情缓存，数据仍处于有效刷新窗口。",
                "is_stale": False,
            }
        )
    _increment("hits")
    _increment("stale_hits")
    return snapshot.model_copy(
        update={
            "data_source": snapshot.data_source or "local_quote_cache",
            "source_quality": "stale",
            "data_quality": "stale",
            "data_quality_message": f"来自本地行情缓存，最近刷新于 {int(age_seconds)} 秒前。",
            "is_stale": True,
        }
    )


def write_local_quote_snapshot(snapshot: QuoteSnapshot, ttl_seconds: int = _LOCAL_QUOTE_TTL_SECONDS) -> None:
    if not snapshot.symbol:
        return
    _increment("writes")
    set_json_cache(
        _cache_key(snapshot.symbol),
        _cache_payload(snapshot),
        ttl_seconds=ttl_seconds,
    )


def write_local_quote_snapshots(snapshots: dict[str, QuoteSnapshot], ttl_seconds: int = _LOCAL_QUOTE_TTL_SECONDS) -> int:
    payloads: dict[str, Any] = {}
    for symbol, snapshot in snapshots.items():
        target_symbol = str(symbol or snapshot.symbol or "").strip()
        if not target_symbol:
            continue
        payloads[_cache_key(target_symbol)] = _cache_payload(snapshot)
    if not payloads:
        return 0
    written = set_many_json_cache(payloads, ttl_seconds=ttl_seconds)
    if written:
        _increment_by("writes", written)
    return written


def local_quote_cache_key(symbol: str) -> str:
    return _cache_key(symbol)


def local_quote_cache_metrics_snapshot() -> dict[str, int]:
    with _LOCK:
        return dict(_METRICS)


def _cache_key(symbol: str) -> str:
    return f"tquant:market:quote:{symbol.strip()}"


def _cache_payload(snapshot: QuoteSnapshot) -> dict[str, Any]:
    return {
        "cached_at": time.time(),
        "payload": snapshot.model_dump(mode="json"),
    }


def _increment(key: str) -> None:
    _increment_by(key, 1)


def _increment_by(key: str, count: int) -> None:
    with _LOCK:
        _METRICS[key] = int(_METRICS.get(key) or 0) + int(count)


def _parse_payload(raw: Any) -> tuple[QuoteSnapshot | None, float]:
    try:
        if isinstance(raw, dict) and isinstance(raw.get("payload"), dict):
            snapshot = QuoteSnapshot.model_validate(raw.get("payload"))
            return snapshot, float(raw.get("cached_at") or 0.0)
        if isinstance(raw, dict):
            snapshot = QuoteSnapshot.model_validate(raw)
            return snapshot, 0.0
    except Exception:
        return None, 0.0
    return None, 0.0
