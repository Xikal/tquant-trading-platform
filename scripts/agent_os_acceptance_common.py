from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

DEFAULT_OUTPUT = PROJECT_ROOT / "research" / "reports" / "agent_os_acceptance.json"
DEFAULT_DATASET = PROJECT_ROOT / "research" / "reports" / "datasets" / "agent_strategy_samples.csv"
DEFAULT_STRATEGY_REPORT = PROJECT_ROOT / "research" / "reports" / "agent_strategy_validation.json"
DEFAULT_BENCHMARK_REPORT = PROJECT_ROOT / "research" / "reports" / "agent_benchmark.json"
DEFAULT_ORCHESTRATION = PROJECT_ROOT / "docs" / "hermes_orchestration.yaml"


@dataclass(frozen=True)
class StepResult:
    name: str
    status: str
    ok: bool
    message: str
    data: dict[str, Any]
    duration_ms: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "ok": self.ok,
            "message": self.message,
            "duration_ms": self.duration_ms,
            "data": self.data,
        }


def timed(name: str, fn: Callable[[], tuple[str, str, dict[str, Any]]]) -> StepResult:
    started = time.perf_counter()
    try:
        status, message, data = fn()
    except Exception as exc:  # noqa: BLE001
        status, message, data = "failed", f"{name} 执行异常：{exc}", {}
    duration_ms = int((time.perf_counter() - started) * 1000)
    return StepResult(
        name=name,
        status=status,
        ok=status in {"ok", "empty", "not_configured", "degraded"},
        message=message,
        data=data,
        duration_ms=duration_ms,
    )


def overall_status(steps: list[StepResult]) -> str:
    if any(not item.ok for item in steps):
        return "failed"
    if any(item.status in {"not_configured", "degraded", "empty"} for item in steps):
        return "degraded"
    return "ok"


def summary(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "overall_status": report.get("overall_status"),
        "steps": [
            {
                "name": item.get("name"),
                "status": item.get("status"),
                "message": item.get("message"),
                "duration_ms": item.get("duration_ms"),
            }
            for item in report.get("steps", [])
        ],
    }
