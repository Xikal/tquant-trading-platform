from __future__ import annotations

from typing import Any

from app.services.market.parameter_defaults import (
    MARKET_DISTRIBUTION_SIGNAL_DEFAULTS,
    MARKET_INTRADAY_ANOMALY_DEFAULTS,
    MARKET_SECTOR_ETF_T0_DEFAULTS,
    POSITION_T_INTRADAY_STRUCTURE_DEFAULTS,
)
from app.services.low_buy.strategy_parameter_defaults_parts.low_buy import (
    LOW_BUY_AUTO_GOVERNANCE_DEFAULTS,
    LOW_BUY_DYNAMIC_ADJUSTMENT_DEFAULTS,
    LOW_BUY_HARD_RISK_DEFAULTS,
    LOW_BUY_RESEARCH_LAYER_DEFAULTS,
    LOW_BUY_SCORING_DEFAULTS,
    LOW_BUY_STRATEGY_EXECUTION_DEFAULTS,
    LOW_BUY_STRATEGY_PREFILTER_DEFAULTS,
    LOW_BUY_THRESHOLD_DEFAULTS,
)
from app.services.low_buy.strategy_parameter_defaults_parts.market import MARKET_REGIME_SCORING_DEFAULTS
from app.services.low_buy.strategy_parameter_defaults_parts.position_t import (
    POSITION_T_DECISION_DEFAULTS,
    POSITION_T_SCORING_DEFAULTS,
)
from app.services.low_buy.strategy_parameter_defaults_parts.runtime import (
    BACKTEST_EXECUTION_DEFAULTS,
    CAPACITY_ANALYSIS_DEFAULTS,
    ML_SIGNAL_TRAINING_DEFAULTS,
    PAPER_DYNAMIC_EXIT_DEFAULTS,
    PAPER_RISK_CONTROL_DEFAULTS,
    RISK_VOLATILITY_SIZING_DEFAULTS,
)


def quant_parameter_schema() -> dict[str, Any]:
    """Return a lightweight machine-readable schema for editable parameters."""

    return {
        "risk.max_single_position_pct": _field_schema(0.3, "risk.max_single_position_pct"),
        "risk.max_total_exposure_pct": _field_schema(0.8, "risk.max_total_exposure_pct"),
        "risk.default_stop_loss_pct": _field_schema(-3.0, "risk.default_stop_loss_pct"),
        "risk.default_take_profit_pct": _field_schema(4.5, "risk.default_take_profit_pct"),
        "low_buy.min_priority_score": _field_schema(75, "low_buy.min_priority_score"),
        "low_buy.max_candidates_per_day": _field_schema(12, "low_buy.max_candidates_per_day"),
        "low_buy.entry_zone_buffer_pct": _field_schema(0.8, "low_buy.entry_zone_buffer_pct"),
        "low_buy.stale_quote_seconds": _field_schema(90, "low_buy.stale_quote_seconds"),
        "low_buy.strategy_prefilters": {
            strategy: {
                key: _field_schema(value, f"low_buy.strategy_prefilters.{strategy}.{key}")
                for key, value in params.items()
            }
            for strategy, params in LOW_BUY_STRATEGY_PREFILTER_DEFAULTS.items()
        },
        "low_buy.strategy_execution": {
            strategy: {
                key: _field_schema(value, f"low_buy.strategy_execution.{strategy}.{key}")
                for key, value in params.items()
            }
            for strategy, params in LOW_BUY_STRATEGY_EXECUTION_DEFAULTS.items()
        },
        "low_buy.scoring": _nested_schema(LOW_BUY_SCORING_DEFAULTS, "low_buy.scoring"),
        "low_buy.thresholds": _nested_schema(LOW_BUY_THRESHOLD_DEFAULTS, "low_buy.thresholds"),
        "low_buy.auto_governance": _nested_schema(LOW_BUY_AUTO_GOVERNANCE_DEFAULTS, "low_buy.auto_governance"),
        "low_buy.research_layers": _nested_schema(LOW_BUY_RESEARCH_LAYER_DEFAULTS, "low_buy.research_layers"),
        "low_buy.hard_risk": _nested_schema(LOW_BUY_HARD_RISK_DEFAULTS, "low_buy.hard_risk"),
        "low_buy.dynamic_adjustment": _nested_schema(LOW_BUY_DYNAMIC_ADJUSTMENT_DEFAULTS, "low_buy.dynamic_adjustment"),
        "low_buy.market_state_rules": {
            "default_state_rules": {"type": "object", "default": {}, "description": "市场状态默认规则覆盖。", "risk_level": "high"},
            "strategy_overrides": {"type": "object", "default": {}, "description": "按策略和市场状态覆盖执行规则。", "risk_level": "high"},
            "severity_penalty_scale": {"type": "object", "default": {}, "description": "市场强度惩罚系数覆盖。", "risk_level": "high"},
            "directional_bias": {"type": "object", "default": {}, "description": "正T/反T方向偏置阈值覆盖。", "risk_level": "high"},
        },
        "position_t.positive_t_min_edge_pct": _field_schema(1.2, "position_t.positive_t_min_edge_pct"),
        "position_t.negative_t_min_risk_pct": _field_schema(1.0, "position_t.negative_t_min_risk_pct"),
        "position_t.min_available_lot": _field_schema(100, "position_t.min_available_lot"),
        "position_t.scoring": _nested_schema(POSITION_T_SCORING_DEFAULTS, "position_t.scoring"),
        "position_t.decision": _nested_schema(POSITION_T_DECISION_DEFAULTS, "position_t.decision"),
        "position_t.intraday_structure": _nested_schema(
            POSITION_T_INTRADAY_STRUCTURE_DEFAULTS,
            "position_t.intraday_structure",
        ),
        "market.regime_scoring": _nested_schema(MARKET_REGIME_SCORING_DEFAULTS, "market.regime_scoring"),
        "market.sector_etf_t0": _nested_schema(MARKET_SECTOR_ETF_T0_DEFAULTS, "market.sector_etf_t0"),
        "market.intraday_anomaly": _nested_schema(MARKET_INTRADAY_ANOMALY_DEFAULTS, "market.intraday_anomaly"),
        "market.distribution_signals": _nested_schema(
            MARKET_DISTRIBUTION_SIGNAL_DEFAULTS,
            "market.distribution_signals",
        ),
        "risk.volatility_sizing": _nested_schema(RISK_VOLATILITY_SIZING_DEFAULTS, "risk.volatility_sizing"),
        "paper.dynamic_exit": _nested_schema(PAPER_DYNAMIC_EXIT_DEFAULTS, "paper.dynamic_exit"),
        "paper.risk_control": _nested_schema(PAPER_RISK_CONTROL_DEFAULTS, "paper.risk_control"),
        "ml.production_enabled": _field_schema(False, "ml.production_enabled"),
        "ml.min_oos_days": _field_schema(60, "ml.min_oos_days"),
        "ml.min_samples": _field_schema(1000, "ml.min_samples"),
        "ml.training": _nested_schema(ML_SIGNAL_TRAINING_DEFAULTS, "ml.training"),
        "backtest.execution": _nested_schema(BACKTEST_EXECUTION_DEFAULTS, "backtest.execution"),
        "capacity": _nested_schema(CAPACITY_ANALYSIS_DEFAULTS, "capacity"),
    }


def _field_schema(value: Any, path: str = "") -> dict[str, Any]:
    if isinstance(value, list):
        return {
            "type": "array",
            "default": value,
            **_bounds_for_path(path, value),
            "description": "策略运行参数，修改后下一次扫描生效。",
            "risk_level": "medium",
        }
    kind = (
        "boolean"
        if isinstance(value, bool)
        else "number"
        if isinstance(value, float)
        else "integer"
        if isinstance(value, int)
        else "string"
    )
    bounds = _bounds_for_path(path, value)
    return {
        "type": kind,
        "default": value,
        "min": bounds.get("min"),
        "max": bounds.get("max"),
        "description": "策略运行参数，修改后下一次扫描生效。",
        "risk_level": "medium",
    }


def _nested_schema(values: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in values.items():
        path = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict):
            result[key] = _nested_schema(value, path)
        elif isinstance(value, list):
            result[key] = {
                "type": "array",
                "default": value,
                **_bounds_for_path(path, value),
                "description": "策略运行参数，修改后下一次扫描生效。",
                "risk_level": "medium",
            }
        else:
            result[key] = _field_schema(value, path)
    return result


def _bounds_for_path(path: str, value: Any) -> dict[str, float | int | None]:
    """Conservative safety bounds for editable runtime parameters.

    These bounds are intentionally broad enough for normal strategy tuning but
    narrow enough to reject obviously destructive values such as 999% stops or
    million-point scoring weights.
    """

    if not _contains_numeric(value):
        return {"min": None, "max": None}
    normalized = path.lower()
    leaf = normalized.split(".")[-1]
    if "sector_proxy_map" in normalized:
        return {"min": None, "max": None}
    if "market_state_rules" in normalized:
        return {"min": -200.0, "max": 200.0}
    if any(token in leaf for token in ("weight", "bonus", "penalty", "shift")):
        return {"min": -1000.0, "max": 1000.0}
    if any(token in leaf for token in ("score", "confidence", "health")):
        return {"min": 0.0, "max": 100.0}
    if "bps" in leaf:
        return {"min": 0.0, "max": 1000.0}
    if "rate" in leaf:
        return {"min": -100.0, "max": 100.0}
    if any(token in leaf for token in ("pct", "percent")):
        min_value = -100.0 if any(token in leaf for token in ("loss", "drawdown", "adverse", "down")) else 0.0
        return {"min": min_value, "max": 100.0}
    if any(token in leaf for token in ("ratio", "multiplier")):
        return {"min": 0.0, "max": 10.0}
    if any(token in leaf for token in ("days", "lookback")):
        return {"min": 0, "max": 3650}
    if "seconds" in leaf:
        return {"min": 0, "max": 86400}
    if any(token in leaf for token in ("window", "bars", "period")):
        return {"min": 0, "max": 10000}
    if any(token in leaf for token in ("count", "limit", "samples", "signals", "orders", "candidates")):
        return {"min": 0, "max": 1_000_000}
    if any(token in leaf for token in ("amount", "cash", "turnover", "volume")):
        return {"min": 0.0, "max": 1_000_000_000_000.0}
    if isinstance(value, (int, float)) and value >= 0:
        return {"min": 0.0, "max": 1_000_000.0}
    return {"min": -1_000_000.0, "max": 1_000_000.0}


def _contains_numeric(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, list):
        return any(_contains_numeric(item) for item in value)
    return False
