from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class ProviderCircuitConfig:
    failure_threshold: int = 3
    cooldown_seconds: int = 60
    slow_call_ms: int = 3000


@dataclass
class ProviderMetrics:
    calls: int = 0
    successes: int = 0
    failures: int = 0
    slow_calls: int = 0
    total_latency_ms: int = 0
    last_error: str = ""


@dataclass
class ProviderCircuitState:
    failure_count: int = 0
    opened_until: float = 0.0
    half_open_probe: bool = False


_GLOBAL_LOCK = threading.RLock()
_GLOBAL_STATES: dict[str, ProviderCircuitState] = {}
_GLOBAL_METRICS: dict[str, ProviderMetrics] = {}


class ProviderCircuitRegistry:
    """In-process circuit breaker and lightweight provider metrics."""

    def __init__(self, config: ProviderCircuitConfig) -> None:
        self.config = config
        self._lock = _GLOBAL_LOCK
        self._states = _GLOBAL_STATES
        self._metrics = _GLOBAL_METRICS

    def can_call(self, provider_name: str, operation: str) -> bool:
        key = self._key(provider_name, operation)
        with self._lock:
            state = self._states.get(key)
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
        with self._lock:
            metric = self._metrics.setdefault(key, ProviderMetrics())
            metric.calls += 1
            metric.total_latency_ms += max(int(latency_ms), 0)
            if latency_ms >= self.config.slow_call_ms:
                metric.slow_calls += 1
            if ok:
                metric.successes += 1
                self._states[key] = ProviderCircuitState()
                return
            metric.failures += 1
            metric.last_error = error[:160]
            state = self._states.setdefault(key, ProviderCircuitState())
            state.failure_count += 1
            state.half_open_probe = False
            if state.failure_count >= max(self.config.failure_threshold, 1):
                state.opened_until = time.monotonic() + max(self.config.cooldown_seconds, 1)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            providers = {
                key: _metric_out(item, self._states.get(key, ProviderCircuitState()))
                for key, item in self._metrics.items()
            }
            totals = _totals(self._metrics)
            return {
                **totals,
                "providers": providers,
            }

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
    with _GLOBAL_LOCK:
        return {
            **_totals(_GLOBAL_METRICS),
            "providers": {
                key: _metric_out(item, _GLOBAL_STATES.get(key, ProviderCircuitState()))
                for key, item in _GLOBAL_METRICS.items()
            },
        }
