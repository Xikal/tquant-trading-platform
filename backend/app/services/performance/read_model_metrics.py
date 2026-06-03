from __future__ import annotations

import json
import threading
import time
from collections import defaultdict
from typing import Any

from pydantic import BaseModel

from app.core.config import get_settings

_LOCK = threading.RLock()
_COUNTERS: dict[str, defaultdict[str, int]] = {
    "read_model_cache_hits": defaultdict(int),
    "read_model_cache_misses": defaultdict(int),
    "read_model_cache_writes": defaultdict(int),
    "read_model_cache_stale": defaultdict(int),
    "live_overlay_hits": defaultdict(int),
    "live_overlay_misses": defaultdict(int),
}
_GAUGES: dict[str, defaultdict[str, float]] = {
    "read_model_cache_age_seconds": defaultdict(float),
    "response_item_count": defaultdict(float),
    "response_bytes": defaultdict(float),
    "response_serialization_ms": defaultdict(float),
}


def record_read_model_cache_hit(model: str, *, age_seconds: float = 0.0) -> None:
    _increment("read_model_cache_hits", model)
    _set_gauge("read_model_cache_age_seconds", model, max(float(age_seconds or 0.0), 0.0))


def record_read_model_cache_miss(model: str) -> None:
    _increment("read_model_cache_misses", model)


def record_read_model_cache_write(model: str) -> None:
    _increment("read_model_cache_writes", model)


def record_read_model_cache_stale(model: str) -> None:
    _increment("read_model_cache_stale", model)


def record_live_overlay_hit(source: str) -> None:
    _increment("live_overlay_hits", source)


def record_live_overlay_miss(source: str) -> None:
    _increment("live_overlay_misses", source)


def record_response_payload(route: str, payload: Any, *, item_count: int | None = None) -> None:
    if not get_settings().response_payload_metrics_enabled:
        return
    started = time.perf_counter()
    try:
        raw = _json_payload(payload)
    except Exception:
        return
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    _set_gauge("response_item_count", route, float(item_count if item_count is not None else _infer_item_count(payload)))
    _set_gauge("response_bytes", route, float(len(raw.encode("utf-8"))))
    _set_gauge("response_serialization_ms", route, elapsed_ms)


def read_model_metrics_snapshot() -> dict[str, dict[str, float]]:
    with _LOCK:
        snapshot: dict[str, dict[str, float]] = {}
        for key, values in _COUNTERS.items():
            snapshot[key] = {label: float(value) for label, value in values.items()}
        for key, values in _GAUGES.items():
            snapshot[key] = {label: float(value) for label, value in values.items()}
        return snapshot


def reset_read_model_metrics() -> None:
    with _LOCK:
        for values in _COUNTERS.values():
            values.clear()
        for values in _GAUGES.values():
            values.clear()


def _increment(group: str, label: str) -> None:
    clean = _clean_label(label)
    with _LOCK:
        _COUNTERS[group][clean] += 1


def _set_gauge(group: str, label: str, value: float) -> None:
    clean = _clean_label(label)
    with _LOCK:
        _GAUGES[group][clean] = float(value)


def _json_payload(payload: Any) -> str:
    if isinstance(payload, BaseModel):
        return payload.model_dump_json()
    return json.dumps(payload, ensure_ascii=False, default=str, separators=(",", ":"))


def _infer_item_count(payload: Any) -> int:
    if isinstance(payload, BaseModel):
        items = getattr(payload, "items", None)
        if isinstance(items, list):
            return len(items)
    if isinstance(payload, dict):
        items = payload.get("items")
        if isinstance(items, list):
            return len(items)
    return 0


def _clean_label(value: str) -> str:
    return str(value or "unknown").replace('"', "").replace("\\", "_")[:80]

