from __future__ import annotations

import time
import threading
from copy import deepcopy
from typing import Any

from app.core.database import SessionLocal
from app.services.quant.parameter_version_service import QuantParameterVersionService, default_quant_parameters

_CACHE_TTL_SECONDS = 30.0
_CACHE_EXPIRES_AT: dict[str, float] = {}
_CACHE_PARAMS: dict[str, dict[str, Any]] = {}
_CACHE_LOCK = threading.RLock()


def current_quant_parameters(market_state_scope: str = "") -> dict[str, Any]:
    now = time.monotonic()
    cache_key = market_state_scope.strip() or "__default__"
    with _CACHE_LOCK:
        if cache_key in _CACHE_PARAMS and now < _CACHE_EXPIRES_AT.get(cache_key, 0.0):
            return deepcopy(_CACHE_PARAMS[cache_key])
        try:
            with SessionLocal() as db:
                current = QuantParameterVersionService(db).current(
                    scope="low_buy",
                    market_state_scope=market_state_scope,
                )
                params = _deep_merge(default_quant_parameters(), current.params)
        except Exception:
            params = default_quant_parameters()
        _CACHE_PARAMS[cache_key] = params
        _CACHE_EXPIRES_AT[cache_key] = now + _CACHE_TTL_SECONDS
        return deepcopy(params)


def clear_quant_parameter_cache() -> None:
    with _CACHE_LOCK:
        _CACHE_EXPIRES_AT.clear()
        _CACHE_PARAMS.clear()


def get_low_buy_strategy_prefilter(strategy: str, fallback: dict[str, Any]) -> dict[str, Any]:
    return _strategy_config("strategy_prefilters", strategy, fallback)


def get_low_buy_strategy_execution(strategy: str, fallback: dict[str, Any]) -> dict[str, Any]:
    return _strategy_config("strategy_execution", strategy, fallback)


def get_low_buy_scoring() -> dict[str, Any]:
    values = current_quant_parameters().get("low_buy", {}).get("scoring", {})
    return deepcopy(values) if isinstance(values, dict) else {}


def get_low_buy_thresholds() -> dict[str, Any]:
    values = current_quant_parameters().get("low_buy", {}).get("thresholds", {})
    return deepcopy(values) if isinstance(values, dict) else {}


def get_low_buy_auto_governance() -> dict[str, Any]:
    values = current_quant_parameters().get("low_buy", {}).get("auto_governance", {})
    return deepcopy(values) if isinstance(values, dict) else {}


def get_low_buy_research_layers() -> dict[str, Any]:
    values = current_quant_parameters().get("low_buy", {}).get("research_layers", {})
    return deepcopy(values) if isinstance(values, dict) else {}


def get_low_buy_hard_risk() -> dict[str, Any]:
    values = current_quant_parameters().get("low_buy", {}).get("hard_risk", {})
    return deepcopy(values) if isinstance(values, dict) else {}


def get_low_buy_dynamic_adjustment() -> dict[str, Any]:
    values = current_quant_parameters().get("low_buy", {}).get("dynamic_adjustment", {})
    return deepcopy(values) if isinstance(values, dict) else {}


def get_low_buy_market_state_rules() -> dict[str, Any]:
    values = current_quant_parameters().get("low_buy", {}).get("market_state_rules", {})
    return deepcopy(values) if isinstance(values, dict) else {}


def get_low_buy_hard_buy_min_scores() -> dict[str, float]:
    values = (
        current_quant_parameters()
        .get("low_buy", {})
        .get("signal_thresholds", {})
        .get("hard_buy_min_scores", {})
    )
    return {str(key): float(value) for key, value in values.items()} if isinstance(values, dict) else {}


def get_low_buy_soft_buy_min_scores() -> dict[str, dict[str, float]]:
    values = (
        current_quant_parameters()
        .get("low_buy", {})
        .get("signal_thresholds", {})
        .get("soft_buy_min_scores", {})
    )
    if not isinstance(values, dict):
        return {}
    result: dict[str, dict[str, float]] = {}
    for strategy, thresholds in values.items():
        if isinstance(thresholds, dict):
            result[str(strategy)] = {str(key): float(value) for key, value in thresholds.items()}
    return result


def get_position_t_scoring() -> dict[str, Any]:
    values = current_quant_parameters().get("position_t", {}).get("scoring", {})
    return deepcopy(values) if isinstance(values, dict) else {}


def get_position_t_decision() -> dict[str, Any]:
    values = current_quant_parameters().get("position_t", {}).get("decision", {})
    return deepcopy(values) if isinstance(values, dict) else {}


def get_position_t_intraday_structure() -> dict[str, Any]:
    values = current_quant_parameters().get("position_t", {}).get("intraday_structure", {})
    return deepcopy(values) if isinstance(values, dict) else {}


def get_market_regime_scoring() -> dict[str, Any]:
    values = current_quant_parameters().get("market", {}).get("regime_scoring", {})
    return deepcopy(values) if isinstance(values, dict) else {}


def get_market_sector_etf_t0() -> dict[str, Any]:
    values = current_quant_parameters().get("market", {}).get("sector_etf_t0", {})
    return deepcopy(values) if isinstance(values, dict) else {}


def get_market_intraday_anomaly() -> dict[str, Any]:
    values = current_quant_parameters().get("market", {}).get("intraday_anomaly", {})
    return deepcopy(values) if isinstance(values, dict) else {}


def get_market_distribution_signals() -> dict[str, Any]:
    values = current_quant_parameters().get("market", {}).get("distribution_signals", {})
    return deepcopy(values) if isinstance(values, dict) else {}


def get_ml_signal_training() -> dict[str, Any]:
    values = current_quant_parameters().get("ml", {}).get("training", {})
    return deepcopy(values) if isinstance(values, dict) else {}


def get_backtest_execution() -> dict[str, Any]:
    values = current_quant_parameters().get("backtest", {}).get("execution", {})
    return deepcopy(values) if isinstance(values, dict) else {}


def get_capacity_analysis() -> dict[str, Any]:
    values = current_quant_parameters().get("capacity", {})
    return deepcopy(values) if isinstance(values, dict) else {}


def get_risk_volatility_sizing() -> dict[str, Any]:
    values = current_quant_parameters().get("risk", {}).get("volatility_sizing", {})
    return deepcopy(values) if isinstance(values, dict) else {}


def get_paper_dynamic_exit() -> dict[str, Any]:
    values = current_quant_parameters().get("paper", {}).get("dynamic_exit", {})
    return deepcopy(values) if isinstance(values, dict) else {}


def _strategy_config(section: str, strategy: str, fallback: dict[str, Any]) -> dict[str, Any]:
    values = current_quant_parameters().get("low_buy", {}).get(section, {}).get(strategy, {})
    if not isinstance(values, dict):
        values = {}
    return _deep_merge(fallback, values)


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
