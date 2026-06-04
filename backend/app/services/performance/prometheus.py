from __future__ import annotations

from app.services.performance.read_model_metrics import read_model_metrics_snapshot
from app.services.read_models.indicator_cache import indicator_cache_metrics_snapshot


def performance_prometheus_lines() -> list[str]:
    return [
        *read_model_prometheus_lines(),
        *indicator_cache_prometheus_lines(),
    ]


def read_model_prometheus_lines() -> list[str]:
    snapshot = read_model_metrics_snapshot()
    lines: list[str] = [
        "# HELP tquant_read_model_cache_hits_total Read model cache hits by model.",
        "# TYPE tquant_read_model_cache_hits_total counter",
    ]
    lines.extend(_labeled("tquant_read_model_cache_hits_total", "model", snapshot.get("read_model_cache_hits", {})))
    lines.extend(
        [
            "# HELP tquant_read_model_cache_misses_total Read model cache misses by model.",
            "# TYPE tquant_read_model_cache_misses_total counter",
        ]
    )
    lines.extend(_labeled("tquant_read_model_cache_misses_total", "model", snapshot.get("read_model_cache_misses", {})))
    lines.extend(
        [
            "# HELP tquant_read_model_cache_writes_total Read model cache writes by model.",
            "# TYPE tquant_read_model_cache_writes_total counter",
        ]
    )
    lines.extend(_labeled("tquant_read_model_cache_writes_total", "model", snapshot.get("read_model_cache_writes", {})))
    lines.extend(
        [
            "# HELP tquant_read_model_cache_stale_total Expired read model cache entries by model.",
            "# TYPE tquant_read_model_cache_stale_total counter",
        ]
    )
    lines.extend(_labeled("tquant_read_model_cache_stale_total", "model", snapshot.get("read_model_cache_stale", {})))
    lines.extend(
        [
            "# HELP tquant_read_model_cache_age_seconds Last read model cache hit age by model.",
            "# TYPE tquant_read_model_cache_age_seconds gauge",
        ]
    )
    lines.extend(_labeled("tquant_read_model_cache_age_seconds", "model", snapshot.get("read_model_cache_age_seconds", {})))
    lines.extend(
        [
            "# HELP tquant_live_overlay_hits_total Live quote overlay cache hits by source.",
            "# TYPE tquant_live_overlay_hits_total counter",
        ]
    )
    lines.extend(_labeled("tquant_live_overlay_hits_total", "source", snapshot.get("live_overlay_hits", {})))
    lines.extend(
        [
            "# HELP tquant_live_overlay_misses_total Live quote overlay cache misses by source.",
            "# TYPE tquant_live_overlay_misses_total counter",
        ]
    )
    lines.extend(_labeled("tquant_live_overlay_misses_total", "source", snapshot.get("live_overlay_misses", {})))
    lines.extend(
        [
            "# HELP tquant_response_item_count Last hot response item count by route.",
            "# TYPE tquant_response_item_count gauge",
        ]
    )
    lines.extend(_labeled("tquant_response_item_count", "route", snapshot.get("response_item_count", {})))
    lines.extend(
        [
            "# HELP tquant_response_bytes Last hot response serialized byte size by route.",
            "# TYPE tquant_response_bytes gauge",
        ]
    )
    lines.extend(_labeled("tquant_response_bytes", "route", snapshot.get("response_bytes", {})))
    lines.extend(
        [
            "# HELP tquant_response_serialization_ms Last hot response serialization observation by route.",
            "# TYPE tquant_response_serialization_ms gauge",
        ]
    )
    lines.extend(_labeled("tquant_response_serialization_ms", "route", snapshot.get("response_serialization_ms", {})))
    lines.extend(
        [
            "# HELP tquant_bff_partial_source_failures_total BFF partial source failures by bounded source and reason.",
            "# TYPE tquant_bff_partial_source_failures_total counter",
        ]
    )
    lines.extend(_labeled_source_reason("tquant_bff_partial_source_failures_total", snapshot.get("bff_partial_source_failures", {})))
    lines.extend(
        [
            "# HELP tquant_cache_operation_errors_total Cache operation errors by cache, operation, and reason.",
            "# TYPE tquant_cache_operation_errors_total counter",
        ]
    )
    lines.extend(_labeled_cache_operation_reason("tquant_cache_operation_errors_total", snapshot.get("cache_operation_errors", {})))
    return lines


def indicator_cache_prometheus_lines() -> list[str]:
    snapshot = indicator_cache_metrics_snapshot()
    lines = [
        "# HELP tquant_indicator_cache_hits_total Versioned derived indicator cache hits by indicator.",
        "# TYPE tquant_indicator_cache_hits_total counter",
    ]
    lines.extend(_labeled("tquant_indicator_cache_hits_total", "indicator", snapshot.get("hits", {})))
    lines.extend(
        [
            "# HELP tquant_indicator_cache_misses_total Versioned derived indicator cache misses by indicator.",
            "# TYPE tquant_indicator_cache_misses_total counter",
        ]
    )
    lines.extend(_labeled("tquant_indicator_cache_misses_total", "indicator", snapshot.get("misses", {})))
    lines.extend(
        [
            "# HELP tquant_indicator_cache_size Versioned derived indicator cache size by indicator.",
            "# TYPE tquant_indicator_cache_size gauge",
        ]
    )
    lines.extend(_labeled("tquant_indicator_cache_size", "indicator", snapshot.get("size", {})))
    return lines


def _labeled(metric: str, label: str, values: dict[str, float]) -> list[str]:
    if not values:
        return [f'{metric}{{{label}="none"}} 0']
    return [f'{metric}{{{label}="{_escape(name)}"}} {value:g}' for name, value in sorted(values.items())]


def _labeled_source_reason(metric: str, values: dict[str, float]) -> list[str]:
    if not values:
        return [f'{metric}{{source="none",reason="none"}} 0']
    lines: list[str] = []
    for name, value in sorted(values.items()):
        source, _, reason = str(name).partition("|")
        lines.append(f'{metric}{{source="{_escape(source)}",reason="{_escape(reason or "other")}"}} {value:g}')
    return lines


def _labeled_cache_operation_reason(metric: str, values: dict[str, float]) -> list[str]:
    if not values:
        return [f'{metric}{{cache="none",operation="none",reason="none"}} 0']
    lines: list[str] = []
    for name, value in sorted(values.items()):
        cache, _, rest = str(name).partition("|")
        operation, _, reason = rest.partition("|")
        lines.append(
            f'{metric}{{cache="{_escape(cache)}",operation="{_escape(operation or "other")}",reason="{_escape(reason or "other")}"}} {value:g}'
        )
    return lines


def _escape(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"')
