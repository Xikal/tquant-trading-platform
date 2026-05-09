from __future__ import annotations

from typing import Any

from app.models.schema_defs.screener import LowBuyStrategyPerformanceOut
from app.services.low_buy.strategy_parameter_defaults import LOW_BUY_AUTO_GOVERNANCE_DEFAULTS
from app.services.quant.runtime_parameters import get_low_buy_auto_governance


def strategy_health(
    performance: LowBuyStrategyPerformanceOut | None,
    governance_params: dict[str, Any] | None = None,
) -> tuple[float, str]:
    params = governance_params or auto_governance_params()
    health_params = section_params(params, "health_score")
    if performance is None or performance.filled_signals <= 0:
        return 0.0, "暂无绩效样本"
    score = 0.0
    score += range_score(
        performance.avg_net_return_pct,
        low=float_param(health_params, "avg_net_return_low", -2.0),
        high=float_param(health_params, "avg_net_return_high", 4.0),
    ) * float_param(health_params, "avg_net_return_weight", 23.0)
    score += range_score(
        performance.profit_factor,
        low=float_param(health_params, "profit_factor_low", 0.6),
        high=float_param(health_params, "profit_factor_high", 2.0),
    ) * float_param(health_params, "profit_factor_weight", 18.0)
    drawdown_cap = max(float_param(health_params, "max_drawdown_abs_cap", 8.0), 0.01)
    score += (
        1.0 - min(abs(min(performance.avg_max_drawdown_5d, 0.0)) / drawdown_cap, 1.0)
    ) * float_param(health_params, "max_drawdown_weight", 16.0)
    filled_cap = max(float_param(health_params, "filled_signals_cap", 50.0), 1.0)
    score += min(performance.filled_signals / filled_cap, 1.0) * float_param(
        health_params, "filled_signals_weight", 16.0
    )
    score += range_score(
        performance.net_win_rate,
        low=float_param(health_params, "net_win_rate_low", -20.0),
        high=float_param(health_params, "net_win_rate_high", 35.0),
    ) * float_param(health_params, "net_win_rate_weight", 12.0)
    score += market_regime_adaptation_score(performance, params) * float_param(
        health_params, "market_adaptation_weight", 15.0
    )
    score -= (
        min(
            max(performance.stop_loss_rate - float_param(health_params, "stop_loss_excess_threshold", 18.0), 0.0),
            float_param(health_params, "stop_loss_excess_cap", 30.0),
        )
        * float_param(health_params, "stop_loss_penalty_weight", 0.45)
    )
    score -= (
        min(
            max(performance.not_filled_rate - float_param(health_params, "not_filled_excess_threshold", 40.0), 0.0),
            float_param(health_params, "not_filled_excess_cap", 40.0),
        )
        * float_param(health_params, "not_filled_penalty_weight", 0.18)
    )
    normalized = round(
        max(
            min(score, float_param(health_params, "score_max", 100.0)),
            float_param(health_params, "score_min", 0.0),
        ),
        1,
    )
    return normalized, health_text(normalized, performance.filled_signals, params)


def evidence_gate_decision(
    strategy_key: str,
    performance: LowBuyStrategyPerformanceOut | None,
    governance_params: dict[str, Any] | None = None,
) -> dict[str, str] | None:
    params = governance_params or auto_governance_params()
    gates = params.get("evidence_gated_strategies")
    if not isinstance(gates, dict):
        return None
    raw_gate = gates.get(strategy_key)
    if not isinstance(raw_gate, dict):
        return None
    min_filled = int(raw_gate.get("min_filled_signals") or 0)
    filled = int(getattr(performance, "filled_signals", 0) or 0)
    if filled >= min_filled:
        return None
    status = str(raw_gate.get("status") or "watch")
    if status not in {"watch", "paused"}:
        status = "watch"
    reason = str(raw_gate.get("reason") or "").strip()
    if not reason:
        reason = f"真实成交样本 {filled}/{min_filled}，暂不放大为强买。"
    return {"status": status, "reason": reason}


def auto_governance_params() -> dict[str, Any]:
    return deep_merge(LOW_BUY_AUTO_GOVERNANCE_DEFAULTS, get_low_buy_auto_governance())


def section_params(params: dict[str, Any], section: str) -> dict[str, Any]:
    fallback = LOW_BUY_AUTO_GOVERNANCE_DEFAULTS.get(section, {})
    values = params.get(section, {})
    if isinstance(fallback, dict) and isinstance(values, dict):
        return deep_merge(fallback, values)
    return fallback if isinstance(fallback, dict) else {}


def float_param(params: dict[str, Any], key: str, fallback: float | None = None) -> float:
    value = params.get(key, fallback)
    return float(value if value is not None else 0.0)


def int_param(params: dict[str, Any], key: str, fallback: int | None = None) -> int:
    value = params.get(key, fallback)
    return int(value if value is not None else 0)


def range_score(value: float, *, low: float, high: float) -> float:
    if high <= low:
        return 0.0
    return max(min((value - low) / (high - low), 1.0), 0.0)


def market_regime_adaptation_score(
    performance: LowBuyStrategyPerformanceOut,
    governance_params: dict[str, Any] | None = None,
) -> float:
    params = section_params(governance_params or auto_governance_params(), "market_adaptation")
    buckets = performance.market_state_attribution
    usable = [bucket for bucket in buckets if bucket.sample_count >= int_param(params, "min_bucket_samples", 5)]
    if not usable:
        return float_param(params, "empty_score", 0.45)

    weighted = 0.0
    total = 0
    for bucket in usable:
        bucket_score = (
            range_score(
                bucket.avg_return_3d,
                low=float_param(params, "return_3d_low", -2.0),
                high=float_param(params, "return_3d_high", 3.0),
            )
            * float_param(params, "return_3d_weight", 0.45)
            + range_score(
                bucket.avg_return_5d,
                low=float_param(params, "return_5d_low", -3.0),
                high=float_param(params, "return_5d_high", 4.0),
            )
            * float_param(params, "return_5d_weight", 0.25)
            + range_score(
                bucket.hit_rate,
                low=float_param(params, "hit_rate_low", 35.0),
                high=float_param(params, "hit_rate_high", 68.0),
            )
            * float_param(params, "hit_rate_weight", 0.30)
        )
        weak_keywords = params.get("weak_state_keywords") or []
        if any(str(keyword) in bucket.label for keyword in weak_keywords):
            bucket_score *= float_param(params, "weak_state_multiplier", 0.85)
        weighted += bucket_score * bucket.sample_count
        total += bucket.sample_count
    return max(min(weighted / max(total, 1), 1.0), 0.0)


def health_text(score: float, filled_signals: int, governance_params: dict[str, Any] | None = None) -> str:
    params = section_params(governance_params or auto_governance_params(), "health_text")
    if filled_signals < int_param(params, "min_filled_signals", 20):
        return "样本不足，仅供参考"
    if score >= float_param(params, "healthy_score", 75.0):
        return "健康，可生产验证"
    if score >= float_param(params, "watch_score", 55.0):
        return "一般，建议降权观察"
    if score >= float_param(params, "restricted_score", 35.0):
        return "偏弱，限制强信号"
    return "较弱，建议研究层"


def deep_merge(defaults: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, default_value in defaults.items():
        override_value = overrides.get(key) if isinstance(overrides, dict) else None
        if isinstance(default_value, dict) and isinstance(override_value, dict):
            result[key] = deep_merge(default_value, override_value)
        elif isinstance(overrides, dict) and key in overrides:
            result[key] = override_value
        else:
            result[key] = default_value
    if isinstance(overrides, dict):
        for key, value in overrides.items():
            if key not in result:
                result[key] = value
    return result
