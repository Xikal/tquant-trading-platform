from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class AutoTraderState:
    running: bool = False
    dry_run: bool = True
    interval_seconds: int = 120
    max_orders_per_cycle: int = 5
    min_score: int = 75
    last_cycle_at: str = ""
    last_cycle_duration_ms: float = 0.0
    last_cycle_passed: int = 0
    last_cycle_filtered: int = 0
    last_cycle_executed: int = 0
    last_cycle_skipped: int = 0
    last_cycle_summary: str = ""
    total_cycles: int = 0
    total_executed: int = 0
    total_errors: int = 0
    circuit_open: bool = False
    circuit_reason: str = ""
    circuit_since: str = ""
    heartbeat_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
