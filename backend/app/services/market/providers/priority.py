from __future__ import annotations

from typing import Any, Iterable


def order_providers_for_operation(providers: Iterable[Any], metrics_snapshot: dict, operation: str) -> list[Any]:
    """Return providers ordered by recent reliability for the requested operation.

    The original configured order remains the tie breaker.  Providers with no
    history stay in their configured order so first-run behavior is unchanged.
    """

    indexed = list(enumerate(providers))
    provider_metrics = metrics_snapshot.get("providers") if isinstance(metrics_snapshot, dict) else {}
    if not isinstance(provider_metrics, dict) or not provider_metrics:
        return [provider for _, provider in indexed]

    return [
        provider
        for _, provider in sorted(
            indexed,
            key=lambda item: _provider_sort_key(item, provider_metrics, operation),
        )
    ]


def _provider_sort_key(item, provider_metrics: dict, operation: str) -> tuple[float, float, int]:
    index, provider = item
    provider_name = getattr(provider, "name", provider.__class__.__name__)
    metrics = provider_metrics.get(f"{provider_name}:{operation}") or {}
    calls = int(metrics.get("calls") or 0)
    if calls <= 0:
        return (0.35, 0.0, index)
    failures = int(metrics.get("failures") or 0)
    slow_calls = int(metrics.get("slow_calls") or 0)
    failure_rate = failures / max(calls, 1)
    slow_rate = slow_calls / max(calls, 1)
    latency = float(metrics.get("avg_latency_ms") or 0.0) / 10000.0
    circuit_penalty = 1.0 if metrics.get("circuit_open") else 0.0
    return (failure_rate + slow_rate * 0.25 + latency + circuit_penalty, latency, index)
