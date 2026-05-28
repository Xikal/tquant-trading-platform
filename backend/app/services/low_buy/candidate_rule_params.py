from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from typing import Any

from app.services.low_buy.candidate_types import CandidateMetrics
from app.services.low_buy.strategy_parameter_defaults import (
    LOW_BUY_STRATEGY_EXECUTION_DEFAULTS,
    LOW_BUY_STRATEGY_PREFILTER_DEFAULTS,
)
from app.services.quant.runtime_parameters import (
    get_low_buy_scoring,
    get_low_buy_strategy_execution,
    get_low_buy_strategy_prefilter,
)


_RESEARCH_PREFILTER_OVERRIDES: ContextVar[dict[str, dict[str, Any]]] = ContextVar(
    "low_buy_research_prefilter_overrides",
    default={},
)


def prefilter_params(strategy: str) -> dict[str, float]:
    defaults = LOW_BUY_STRATEGY_PREFILTER_DEFAULTS.get(strategy, {})
    values = get_low_buy_strategy_prefilter(strategy, defaults)
    overrides = _RESEARCH_PREFILTER_OVERRIDES.get().get(strategy, {})
    if not isinstance(overrides, dict) or not overrides:
        return values
    return _deep_merge(values, overrides)


def execution_params(strategy: str) -> dict[str, float]:
    defaults = LOW_BUY_STRATEGY_EXECUTION_DEFAULTS.get(strategy, {})
    return get_low_buy_strategy_execution(strategy, defaults)


@contextmanager
def research_prefilter_overrides(overrides: dict[str, dict[str, Any]] | None):
    """Temporarily override strategy prefilter params for research backtests."""

    normalized = _normalize_prefilter_overrides(overrides or {})
    token = _RESEARCH_PREFILTER_OVERRIDES.set(normalized)
    try:
        yield
    finally:
        _RESEARCH_PREFILTER_OVERRIDES.reset(token)


def current_research_prefilter_overrides() -> dict[str, dict[str, Any]]:
    return deepcopy(_RESEARCH_PREFILTER_OVERRIDES.get())


def scoring_params() -> dict[str, Any]:
    return get_low_buy_scoring()


def strategy_score_params(strategy: str) -> dict[str, Any]:
    values = scoring_params().get("strategy_bonuses", {}).get(strategy, {})
    return values if isinstance(values, dict) else {}


def float_param(params: dict[str, Any], key: str, fallback: float) -> float:
    try:
        return float(params.get(key, fallback))
    except (TypeError, ValueError):
        return fallback


def int_param(params: dict[str, Any], key: str, fallback: int) -> int:
    try:
        return int(params.get(key, fallback))
    except (TypeError, ValueError):
        return fallback


def ma5_ma10_ma20_confluence_pct(metrics: CandidateMetrics) -> float:
    ma_values = [value for value in (metrics.ma5, metrics.ma10, metrics.ma20) if value > 0]
    if len(ma_values) < 3 or metrics.latest_close <= 0:
        return 99.0
    return (max(ma_values) - min(ma_values)) / metrics.latest_close * 100.0


def _deep_merge(defaults: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, default_value in defaults.items():
        override_value = overrides.get(key)
        if isinstance(default_value, dict) and isinstance(override_value, dict):
            result[key] = _deep_merge(default_value, override_value)
        elif key in overrides:
            result[key] = override_value
        else:
            result[key] = default_value
    for key, value in overrides.items():
        if key not in result:
            result[key] = value
    return result


def _normalize_prefilter_overrides(values: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    normalized: dict[str, dict[str, Any]] = {}
    for raw_strategy, raw_params in values.items():
        strategy = str(raw_strategy or "").strip()
        if not strategy or not isinstance(raw_params, dict):
            continue
        normalized[strategy] = {str(key): value for key, value in raw_params.items()}
    return normalized
