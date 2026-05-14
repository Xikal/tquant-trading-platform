from __future__ import annotations

from dataclasses import replace
from typing import Any

from sqlalchemy.orm import Session

from app.services.low_buy.strategy_governance import latest_strategy_performance_map
from app.services.low_buy.strategy_governance_health import strategy_health
from app.services.low_buy.strategy_validation_phase import resolve_strategy_validation_phase
from app.services.paper.admission import AdmissionResult


def apply_strategy_validation_phase(
    db: Session,
    candidates: list[AdmissionResult],
) -> tuple[list[AdmissionResult], list[AdmissionResult]]:
    if not candidates:
        return [], []
    performance_map = latest_strategy_performance_map(db)
    passed: list[AdmissionResult] = []
    filtered: list[AdmissionResult] = []
    for candidate in candidates:
        strategy_key = _strategy_key(candidate.signal)
        performance = performance_map.get(strategy_key)
        health_score, _ = strategy_health(performance)
        phase = resolve_strategy_validation_phase(performance, health_score)
        signal = _signal_with_phase(candidate.signal, phase)
        updated = replace(candidate, signal=signal)
        if phase.position_scale <= 0:
            filtered.append(replace(updated, passed=False, reason=phase.reason))
        else:
            passed.append(updated)
    return passed, filtered


def _signal_with_phase(signal: dict[str, Any], phase: Any) -> dict[str, Any]:
    payload = dict(signal)
    payload["validation_phase"] = phase.phase
    payload["validation_phase_text"] = phase.phase_text
    payload["validation_phase_reason"] = phase.reason
    payload["validation_position_scale"] = phase.position_scale
    return payload


def _strategy_key(signal: dict[str, Any]) -> str:
    value = signal.get("strategy_key")
    if value:
        return str(value)
    values = signal.get("strategy_keys")
    if isinstance(values, list) and values:
        return str(values[0])
    return ""
