from __future__ import annotations

import threading
from dataclasses import dataclass


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
    open_count: int = 0
    opened_until: float = 0.0
    half_open_probe: bool = False


class ProviderCircuitStore:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.states: dict[str, ProviderCircuitState] = {}
        self.metrics: dict[str, ProviderMetrics] = {}


_GLOBAL_STORE = ProviderCircuitStore()


def global_provider_circuit_store() -> ProviderCircuitStore:
    return _GLOBAL_STORE
