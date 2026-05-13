from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from app.services.market.providers.circuit_state import (
    ProviderCircuitState,
    ProviderCircuitStore,
    ProviderMetrics,
    global_provider_circuit_store,
)


@dataclass
class ProviderCircuitConfig:
    failure_threshold: int = 3
    cooldown_seconds: int = 60
    slow_call_ms: int = 3000


class ProviderCircuitRegistry:
    """In-process circuit breaker with optional isolated state store."""

    def __init__(self, config: ProviderCircuitConfig, store: ProviderCircuitStore | None = None) -> None:
        self.config = config
        self._store = store or global_provider_circuit_store()
        self._lock = self._store.lock
        self._states = self._store.states
        self._metrics = self._store.metrics

    def can_call(self, provider_name: str, operation: str) -> bool:
        key = self._key(provider_name, operation)
        with self._store.lock:
            state = self._store.states.get(key)
            if state is None:
                return True
            if state.opened_until > time.monotonic():
                return False
            if state.failure_count >= max(self.config.failure_threshold, 1):
                if state.half_open_probe:
                    return False
                state.half_open_probe = True
            return True

    def record(self, provider_name: str, operation: str, *, ok: bool, latency_ms: int, error: str = "") -> None:
        key = self._key(provider_name, operation)
        with self._store.lock:
            metric = self._store.metrics.setdefault(key, ProviderMetrics())
            metric.calls += 1
            metric.total_latency_ms += max(int(latency_ms), 0)
            if latency_ms >= self.config.slow_call_ms:
                metric.slow_calls += 1
            if ok:
                metric.successes += 1
                self._store.states[key] = ProviderCircuitState()
                return
            metric.failures += 1
            metric.last_error = error[:160]
            state = self._store.states.setdefault(key, ProviderCircuitState())
            state.failure_count += 1
            state.half_open_probe = False
            if state.failure_count >= max(self.config.failure_threshold, 1):
                state.opened_until = time.monotonic() + max(self.config.cooldown_seconds, 1)

    def snapshot(self) -> dict[str, Any]:
        with self._store.lock:
            providers = {
                key: _metric_out(item, self._store.states.get(key, ProviderCircuitState()))
                for key, item in self._store.metrics.items()
            }
            totals = _totals(self._store.metrics)
            return {**totals, "providers": providers}

    @staticmethod
    def _key(provider_name: str, operation: str) -> str:
        return f"{provider_name}:{operation}"


def _metric_out(item: ProviderMetrics, state: ProviderCircuitState) -> dict[str, Any]:
    return {
        "calls": item.calls,
        "successes": item.successes,
        "failures": item.failures,
        "slow_calls": item.slow_calls,
        "avg_latency_ms": round(item.total_latency_ms / max(item.calls, 1), 2),
        "last_error": item.last_error,
        "circuit_open": state.opened_until > time.monotonic(),
        "half_open_probe": state.half_open_probe,
    }


def _totals(metrics: dict[str, ProviderMetrics]) -> dict[str, int]:
    return {
        "provider_calls_total": sum(item.calls for item in metrics.values()),
        "provider_success_total": sum(item.successes for item in metrics.values()),
        "provider_failures_total": sum(item.failures for item in metrics.values()),
        "provider_slow_calls_total": sum(item.slow_calls for item in metrics.values()),
    }


def provider_metrics_snapshot() -> dict[str, Any]:
    registry = ProviderCircuitRegistry(ProviderCircuitConfig())
    return registry.snapshot()
