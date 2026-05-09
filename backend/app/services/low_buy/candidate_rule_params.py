from __future__ import annotations

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


def prefilter_params(strategy: str) -> dict[str, float]:
    defaults = LOW_BUY_STRATEGY_PREFILTER_DEFAULTS.get(strategy, {})
    return get_low_buy_strategy_prefilter(strategy, defaults)


def execution_params(strategy: str) -> dict[str, float]:
    defaults = LOW_BUY_STRATEGY_EXECUTION_DEFAULTS.get(strategy, {})
    return get_low_buy_strategy_execution(strategy, defaults)


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
