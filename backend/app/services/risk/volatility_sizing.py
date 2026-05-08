from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.low_buy.strategy_parameter_defaults import RISK_VOLATILITY_SIZING_DEFAULTS
from app.services.quant.runtime_parameters import get_risk_volatility_sizing


@dataclass(frozen=True)
class VolatilityPositionCap:
    atr_pct: float
    cap_pct: float
    bucket: str
    reason: str


def build_volatility_position_cap(atr_pct: float | None) -> VolatilityPositionCap:
    """Translate ATR percentage into a configurable position cap.

    The function is intentionally small and deterministic so low-buy signals,
    priority-board display and paper auto-trading use one identical rule.
    """

    params = _params()
    if not bool(params.get("enabled", True)):
        return VolatilityPositionCap(
            atr_pct=round(float(atr_pct or 0.0), 2),
            cap_pct=0.0,
            bucket="disabled",
            reason="波动率仓位控制未启用",
        )

    value = _float(atr_pct, 0.0)
    if value <= 0:
        cap = _float_param(params, "unavailable_position_cap_pct")
        return VolatilityPositionCap(
            atr_pct=0.0,
            cap_pct=_cap_floor(cap, params),
            bucket="unavailable",
            reason=f"ATR 数据不足，按保守仓位上限 {_cap_floor(cap, params):.1f}%",
        )

    low_max = _float_param(params, "low_atr_pct_max")
    medium_max = _float_param(params, "medium_atr_pct_max")
    high_max = _float_param(params, "high_atr_pct_max")
    if value <= low_max:
        cap = _float_param(params, "low_position_cap_pct")
        bucket = "low"
        label = "低波动"
    elif value <= medium_max:
        cap = _float_param(params, "medium_position_cap_pct")
        bucket = "medium"
        label = "中等波动"
    elif value <= high_max:
        cap = _float_param(params, "high_position_cap_pct")
        bucket = "high"
        label = "高波动"
    else:
        cap = _float_param(params, "extreme_position_cap_pct")
        bucket = "extreme"
        label = "极高波动"
    capped = _cap_floor(cap, params)
    return VolatilityPositionCap(
        atr_pct=round(value, 2),
        cap_pct=capped,
        bucket=bucket,
        reason=f"ATR {value:.2f}% 属于{label}，单票仓位上限 {capped:.1f}%",
    )


def _params() -> dict[str, Any]:
    values = get_risk_volatility_sizing()
    return {**RISK_VOLATILITY_SIZING_DEFAULTS, **values} if isinstance(values, dict) else dict(RISK_VOLATILITY_SIZING_DEFAULTS)


def _float_param(params: dict[str, Any], key: str) -> float:
    return _float(params.get(key), float(RISK_VOLATILITY_SIZING_DEFAULTS[key]))


def _float(value: Any, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _cap_floor(value: float, params: dict[str, Any]) -> float:
    floor = _float_param(params, "min_position_cap_pct")
    return round(max(value, floor), 2)
