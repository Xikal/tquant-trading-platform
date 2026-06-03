from __future__ import annotations

import threading
import time
from typing import Any

from app.models.schemas import QuoteSnapshot
from app.services.shared.distributed_cache import get_json_cache, get_many_json_cache, set_json_cache, set_many_json_cache

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
    "coverage_checks": 0,
    "coverage_demand_total": 0,
    "coverage_demand_miss_total": 0,
    "coverage_below_target_total": 0,
    "coverage_ratio_bps": 0,
}


def read_local_quote_snapshot(symbol: str) -> QuoteSnapshot | None:
    _increment("reads")
    payload = get_json_cache(_cache_key(symbol))
    if payload is None:
        _increment("misses")
        return None
    snapshot = _snapshot_from_cache_payload(payload)
    if snapshot is None:
        _increment("misses")
        return None
    return snapshot


def read_local_quote_snapshots(symbols: list[str]) -> dict[str, QuoteSnapshot]:
    requested = []
    seen: set[str] = set()
    for symbol in symbols:
        clean = str(symbol or "").strip()
        if not clean or clean in seen:
            continue
        seen.add(clean)
        requested.append(clean)
    if not requested:
        return {}
    _increment_by("reads", len(requested))
    keys = [_cache_key(symbol) for symbol in requested]
    payloads = get_many_json_cache(keys)
    result: dict[str, QuoteSnapshot] = {}
    for symbol, key in zip(requested, keys):
        payload = payloads.get(key)
        if payload is None:
            _increment("misses")
            continue
        snapshot = _snapshot_from_cache_payload(payload)
        if snapshot is None:
            _increment("misses")
            continue
        result[symbol] = snapshot
    return result


def write_local_quote_snapshot(snapshot: QuoteSnapshot, ttl_seconds: int = _LOCAL_QUOTE_TTL_SECONDS) -> None:
    if not snapshot.symbol:
        return
    _increment("writes")
    set_json_cache(
        _cache_key(snapshot.symbol),
        _cache_payload(snapshot),
        ttl_seconds=ttl_seconds,
    )
    _touch_local_quote_cache_marker()


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
        _touch_local_quote_cache_marker()
    return written


def local_quote_cache_key(symbol: str) -> str:
    return _cache_key(symbol)


def local_quote_cache_marker() -> dict[str, Any]:
    payload = get_json_cache(_marker_key())
    if isinstance(payload, dict):
        return {"version": str(payload.get("version") or ""), "as_of": str(payload.get("as_of") or "")}
    return {"version": "", "as_of": ""}


def local_quote_cache_metrics_snapshot() -> dict[str, int]:
    with _LOCK:
        return dict(_METRICS)


def record_quote_cache_demand_coverage(
    *,
    requested_symbols: list[str],
    cached_symbols: list[str] | set[str],
    target_ratio: float = 0.9,
    unresolved_reasons: dict[str, str] | None = None,
) -> dict[str, Any]:
    raw_requested = [str(item or "").strip() for item in requested_symbols if str(item or "").strip()]
    requested = _clean_symbol_set(requested_symbols)
    cached = _clean_symbol_set(list(cached_symbols))
    covered = requested & cached
    missing = requested - cached
    invalid_symbols = sorted({symbol for symbol in raw_requested if len(symbol) != 6 or not symbol.isdigit()})
    demand_count = len(requested)
    covered_count = len(covered)
    ratio = (covered_count / demand_count) if demand_count else 1.0
    below_target = ratio < max(min(float(target_ratio or 0.9), 1.0), 0.0)
    with _LOCK:
        _METRICS["coverage_checks"] = int(_METRICS.get("coverage_checks") or 0) + 1
        _METRICS["coverage_demand_total"] = int(_METRICS.get("coverage_demand_total") or 0) + demand_count
        _METRICS["coverage_demand_miss_total"] = int(_METRICS.get("coverage_demand_miss_total") or 0) + len(missing)
        if below_target:
            _METRICS["coverage_below_target_total"] = int(_METRICS.get("coverage_below_target_total") or 0) + 1
        _METRICS["coverage_ratio_bps"] = int(round(ratio * 10_000))
    return {
        "demand_count": demand_count,
        "covered_count": covered_count,
        "demand_miss_count": len(missing),
        "coverage_ratio": round(ratio, 6),
        "coverage_ratio_bps": int(round(ratio * 10_000)),
        "coverage_below_target": below_target,
        "alert_code": "quote_cache_coverage_below_target" if below_target else "",
        "missing_symbols_sample": sorted(missing)[:20],
        "unresolved_symbols_sample": _unresolved_symbols_sample(
            missing=missing,
            invalid_symbols=invalid_symbols,
            unresolved_reasons=unresolved_reasons or {},
        ),
    }


def reset_local_quote_cache_metrics() -> None:
    with _LOCK:
        for key in list(_METRICS):
            _METRICS[key] = 0


def _cache_key(symbol: str) -> str:
    return f"tquant:market:quote:{symbol.strip()}"


def _marker_key() -> str:
    return "tquant:market:quote:__marker__"


def _touch_local_quote_cache_marker() -> None:
    now = time.time()
    set_json_cache(
        _marker_key(),
        {
            "version": str(int(now * 1000)),
            "as_of": now,
        },
        ttl_seconds=_LOCAL_QUOTE_TTL_SECONDS,
    )


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


def _clean_symbol_set(symbols: list[str]) -> set[str]:
    return {clean for item in symbols if len(clean := str(item or "").strip()) == 6 and clean.isdigit()}


def _unresolved_symbols_sample(
    *,
    missing: set[str],
    invalid_symbols: list[str],
    unresolved_reasons: dict[str, str],
) -> list[dict[str, str]]:
    sample: list[dict[str, str]] = []
    for symbol in sorted(missing):
        sample.append({"symbol": symbol, "reason": _known_unresolved_reason(unresolved_reasons.get(symbol) or "not_in_cache")})
        if len(sample) >= 20:
            return sample
    for symbol in invalid_symbols:
        sample.append({"symbol": symbol, "reason": "invalid_symbol"})
        if len(sample) >= 20:
            return sample
    return sample


def _known_unresolved_reason(reason: str) -> str:
    value = str(reason or "not_in_cache")
    allowed = {"not_in_cache", "no_daily_bar", "invalid_symbol", "stale_only"}
    return value if value in allowed else "not_in_cache"


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


def _snapshot_from_cache_payload(raw: Any) -> QuoteSnapshot | None:
    snapshot, cached_at = _parse_payload(raw)
    if snapshot is None:
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
