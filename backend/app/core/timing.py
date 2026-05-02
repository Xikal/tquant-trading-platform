from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass
from typing import Any


def monotonic_start() -> float:
    return time.perf_counter()


def log_slow_call(
    logger: logging.Logger,
    operation: str,
    started_at: float,
    *,
    threshold_seconds: float = 2.0,
    **fields: Any,
) -> None:
    duration_ms = int((time.perf_counter() - started_at) * 1000)
    if duration_ms < int(threshold_seconds * 1000):
        return
    safe_fields = {key: value for key, value in fields.items() if value is not None}
    logger.warning(
        "slow_operation operation=%s duration_ms=%s fields=%s",
        operation,
        duration_ms,
        safe_fields,
    )


@dataclass(frozen=True)
class RequestTimingSample:
    method: str
    path: str
    status_code: int
    duration_ms: int
    created_at: float


_REQUEST_TIMINGS: deque[RequestTimingSample] = deque(maxlen=1000)


def record_request_timing(*, method: str, path: str, status_code: int, duration_ms: int) -> None:
    _REQUEST_TIMINGS.append(
        RequestTimingSample(
            method=method,
            path=_normalize_path(path),
            status_code=status_code,
            duration_ms=duration_ms,
            created_at=time.time(),
        )
    )


def request_timing_snapshot() -> dict[str, Any]:
    samples = list(_REQUEST_TIMINGS)
    durations = [item.duration_ms for item in samples]
    slow = [item for item in samples if item.duration_ms >= 3000]
    return {
        "sample_count": len(samples),
        "p50_ms": _percentile(durations, 50),
        "p95_ms": _percentile(durations, 95),
        "p99_ms": _percentile(durations, 99),
        "slow_count": len(slow),
        "slow_latest": [
            {
                "method": item.method,
                "path": item.path,
                "status_code": item.status_code,
                "duration_ms": item.duration_ms,
            }
            for item in slow[-20:]
        ],
        "by_path": _path_summary(samples),
    }


def _path_summary(samples: list[RequestTimingSample]) -> list[dict[str, Any]]:
    buckets: dict[str, list[int]] = {}
    for item in samples:
        buckets.setdefault(f"{item.method} {item.path}", []).append(item.duration_ms)
    rows = []
    for key, values in buckets.items():
        rows.append(
            {
                "route": key,
                "count": len(values),
                "p95_ms": _percentile(values, 95),
                "max_ms": max(values) if values else 0,
            }
        )
    return sorted(rows, key=lambda row: (row["p95_ms"], row["count"]), reverse=True)[:30]


def _percentile(values: list[int], percentile: int) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((percentile / 100) * (len(ordered) - 1))))
    return ordered[index]


def _normalize_path(path: str) -> str:
    parts = []
    for part in path.split("/"):
        if part.isdigit():
            parts.append("{id}")
        else:
            parts.append(part)
    return "/".join(parts) or "/"
