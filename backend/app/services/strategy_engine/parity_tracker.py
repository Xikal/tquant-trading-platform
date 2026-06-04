from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Any


MIN_PARITY_TRADING_DAYS = 30
PARITY_BOUNDARY_NOTE = "非生产采纳依据，仅长期对照"


@dataclass(frozen=True)
class StrategyEngineParityObservation:
    trade_date: str
    strategy_key: str
    symbol: str = ""
    production_priority_score: float | None = None
    strategy_engine_production_score: float | None = None
    production_watch_score: float | None = None
    strategy_engine_watch_score: float | None = None
    parity_status: str = ""
    decision: str = ""
    signal_state: str = ""


def build_strategy_engine_parity_report(
    observations: list[StrategyEngineParityObservation | dict[str, Any]],
    *,
    min_trading_days: int = MIN_PARITY_TRADING_DAYS,
) -> dict[str, Any]:
    rows = [_normalize_observation(item) for item in observations]
    trading_days = sorted({row.trade_date for row in rows if row.trade_date})
    by_strategy = {
        strategy: _stats_for_rows([row for row in rows if row.strategy_key == strategy])
        for strategy in sorted({row.strategy_key for row in rows if row.strategy_key})
    }
    return {
        "status": "ok" if len(trading_days) >= min_trading_days else "insufficient_history",
        "shadow_only": True,
        "replacement_enabled": False,
        "production_adoption_allowed": False,
        "boundary_note": PARITY_BOUNDARY_NOTE,
        "min_trading_days": min_trading_days,
        "trading_day_count": len(trading_days),
        "sample_count": len(rows),
        "window": {
            "start": trading_days[0] if trading_days else "",
            "end": trading_days[-1] if trading_days else "",
        },
        "overall": _stats_for_rows(rows),
        "by_strategy": by_strategy,
    }


def parity_observation_from_shadow_payload(
    payload: dict[str, Any],
    *,
    trade_date: str,
    current_production_score: float | None,
    current_watch_score: float | None,
) -> StrategyEngineParityObservation:
    shadow = dict(payload.get("strategy_engine_shadow") or {})
    return StrategyEngineParityObservation(
        trade_date=trade_date,
        strategy_key=str(shadow.get("strategy_key") or ""),
        symbol=str(shadow.get("symbol") or ""),
        production_priority_score=current_production_score,
        strategy_engine_production_score=_optional_float(shadow.get("production_score")),
        production_watch_score=current_watch_score,
        strategy_engine_watch_score=_optional_float(shadow.get("watch_score")),
        parity_status=str(payload.get("strategy_engine_parity_status") or shadow.get("parity_status") or ""),
        decision=str(payload.get("strategy_engine_decision") or shadow.get("decision") or ""),
        signal_state=str(shadow.get("signal_state") or ""),
    )


def _normalize_observation(item: StrategyEngineParityObservation | dict[str, Any]) -> StrategyEngineParityObservation:
    if isinstance(item, StrategyEngineParityObservation):
        return item
    return StrategyEngineParityObservation(
        trade_date=str(item.get("trade_date") or item.get("date") or ""),
        strategy_key=str(item.get("strategy_key") or ""),
        symbol=str(item.get("symbol") or ""),
        production_priority_score=_optional_float(item.get("production_priority_score") or item.get("priority_score")),
        strategy_engine_production_score=_optional_float(item.get("strategy_engine_production_score")),
        production_watch_score=_optional_float(item.get("production_watch_score") or item.get("watch_score")),
        strategy_engine_watch_score=_optional_float(item.get("strategy_engine_watch_score")),
        parity_status=str(item.get("parity_status") or ""),
        decision=str(item.get("decision") or ""),
        signal_state=str(item.get("signal_state") or ""),
    )


def _stats_for_rows(rows: list[StrategyEngineParityObservation]) -> dict[str, Any]:
    production_deltas = [
        _delta(row.strategy_engine_production_score, row.production_priority_score)
        for row in rows
        if row.strategy_engine_production_score is not None and row.production_priority_score is not None
    ]
    watch_deltas = [
        _delta(row.strategy_engine_watch_score, row.production_watch_score)
        for row in rows
        if row.strategy_engine_watch_score is not None and row.production_watch_score is not None
    ]
    return {
        "sample_count": len(rows),
        "missing_rate_pct": _pct(sum(1 for row in rows if row.strategy_engine_production_score is None), len(rows)),
        "production_zero_rate_pct": _pct(sum(1 for row in rows if row.strategy_engine_production_score == 0), len(rows)),
        "watch_zero_rate_pct": _pct(sum(1 for row in rows if row.strategy_engine_watch_score == 0), len(rows)),
        "match_rate_pct": _pct(sum(1 for row in rows if _row_matches(row)), len(rows)),
        "production_score_delta": _delta_stats(production_deltas),
        "watch_score_delta": _delta_stats(watch_deltas),
        "decision_counts": _counts(row.decision for row in rows),
        "signal_state_counts": _counts(row.signal_state for row in rows),
    }


def _row_matches(row: StrategyEngineParityObservation) -> bool:
    production_match = _nullable_equal(row.strategy_engine_production_score, row.production_priority_score)
    watch_match = _nullable_equal(row.strategy_engine_watch_score, row.production_watch_score)
    return production_match and watch_match


def _delta_stats(values: list[float]) -> dict[str, float | int]:
    if not values:
        return {"count": 0, "avg": 0.0, "max_abs": 0.0, "min": 0.0, "max": 0.0}
    return {
        "count": len(values),
        "avg": round(mean(values), 6),
        "max_abs": round(max(abs(value) for value in values), 6),
        "min": round(min(values), 6),
        "max": round(max(values), 6),
    }


def _counts(values) -> dict[str, int]:  # noqa: ANN001
    result: dict[str, int] = {}
    for raw in values:
        value = str(raw or "").strip() or "unknown"
        result[value] = result.get(value, 0) + 1
    return dict(sorted(result.items()))


def _pct(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(float(numerator) / float(denominator) * 100.0, 4)


def _delta(left: float, right: float) -> float:
    return round(float(left) - float(right), 6)


def _nullable_equal(left: float | None, right: float | None) -> bool:
    if left is None and right is None:
        return True
    if left is None or right is None:
        return False
    return _delta(left, right) == 0.0


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
