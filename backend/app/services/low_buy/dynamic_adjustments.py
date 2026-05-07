from __future__ import annotations

from dataclasses import dataclass

from app.models.schemas import LowBuyCandidateOut, LowBuyStrategyPerformanceOut
from app.services.market.regime import MarketRegimeSnapshot
from app.services.low_buy.shared import LOW_BUY_THRESHOLDS
from app.services.low_buy.strategy_parameter_defaults import LOW_BUY_DYNAMIC_ADJUSTMENT_DEFAULTS
from app.services.quant.runtime_parameters import get_low_buy_dynamic_adjustment


@dataclass(frozen=True)
class LowBuyDynamicAdjustment:
    score_floor_shift: float
    soft_buy_threshold_shift: float
    position_multiplier: float
    reason: str


def low_buy_dynamic_adjustment(
    *,
    market_regime: MarketRegimeSnapshot | None,
    risk_tier: str,
    leader_rank: str,
    performance: LowBuyStrategyPerformanceOut | None = None,
    factor_bonuses: dict[str, float] | None = None,
) -> LowBuyDynamicAdjustment:
    state = market_regime.state if market_regime is not None else "low_volume_wait"
    params = _dynamic_params()
    floor_shift = _market_floor_shift(state)
    position_multiplier = 1.0
    reason_parts = [f"环境 {state}"]

    if risk_tier == "block":
        floor_shift += _float_param(params, "risk_block_shift")
        reason_parts.append("风险阻断")
    elif risk_tier == "degrade":
        floor_shift += _float_param(params, "risk_degrade_shift")
        reason_parts.append("风险降级")

    if leader_rank == "leader":
        floor_shift += _float_param(params, "leader_floor_shift")
        position_multiplier *= _float_param(params, "leader_position_multiplier")
        reason_parts.append("主线龙头加权")
    elif leader_rank == "laggard":
        floor_shift += _float_param(params, "laggard_floor_shift")
        position_multiplier *= _float_param(params, "laggard_position_multiplier")
        reason_parts.append("后排降级")

    if performance is not None:
        performance_shift, performance_multiplier = _performance_adjustment(performance)
        floor_shift += performance_shift
        position_multiplier *= performance_multiplier
        reason_parts.append("绩效归因已接入")

    factor_bonus = min(
        LOW_BUY_THRESHOLDS.MAX_FACTOR_BONUS,
        sum(
            max(float(value), 0.0) * LOW_BUY_THRESHOLDS.FACTOR_WEIGHTS.get(key, 1.0)
            for key, value in (factor_bonuses or {}).items()
        ),
    )
    if factor_bonus > 0:
        floor_shift -= min(
            factor_bonus * _float_param(params, "factor_bonus_floor_weight"),
            _float_param(params, "factor_bonus_floor_cap"),
        )
        reason_parts.append(f"因子加分 +{factor_bonus:.1f}")
    return LowBuyDynamicAdjustment(
        score_floor_shift=round(
            max(_float_param(params, "score_floor_min"), min(_float_param(params, "score_floor_max"), floor_shift)),
            2,
        ),
        soft_buy_threshold_shift=round(
            max(
                _float_param(params, "soft_buy_shift_min"),
                min(_float_param(params, "soft_buy_shift_max"), floor_shift * _float_param(params, "soft_buy_shift_multiplier")),
            ),
            2,
        ),
        position_multiplier=round(
            max(
                _float_param(params, "position_multiplier_min"),
                min(_float_param(params, "position_multiplier_max"), position_multiplier),
            ),
            4,
        ),
        reason=" · ".join(reason_parts),
    )


def apply_performance_adjustment_to_candidate(
    candidate: LowBuyCandidateOut,
    performance: LowBuyStrategyPerformanceOut | None,
) -> LowBuyCandidateOut:
    params = _dynamic_params()
    if performance is None or performance.filled_signals < _int_param(params, "performance_min_filled"):
        return candidate
    _, position_multiplier = _performance_adjustment(performance)
    return candidate.model_copy(
        update={
            "dynamic_position_multiplier": round(candidate.dynamic_position_multiplier * position_multiplier, 4),
        }
    )


def _market_floor_shift(state: str) -> float:
    shifts = _dynamic_params().get("market_floor_shift", {})
    if not isinstance(shifts, dict):
        shifts = LOW_BUY_DYNAMIC_ADJUSTMENT_DEFAULTS["market_floor_shift"]
    return float(shifts.get(state, shifts.get("default", 1.0)))


def _performance_adjustment(performance: LowBuyStrategyPerformanceOut) -> tuple[float, float]:
    params = _dynamic_params()
    filled = max(performance.filled_signals, 0)
    min_filled = _int_param(params, "performance_min_filled")
    if filled < min_filled:
        return 0.0, 1.0
    reliability = min(1.0, (filled - min_filled) / _float_param(params, "performance_reliability_window"))
    if reliability <= 0:
        return 0.0, 1.0
    edge = performance.net_win_rate * _float_param(params, "net_win_rate_weight") + performance.avg_net_return_pct * _float_param(
        params, "avg_return_weight"
    )
    if performance.avg_max_drawdown_5d < _float_param(params, "drawdown_penalty_threshold"):
        edge -= _float_param(params, "drawdown_penalty")
    floor_shift = -max(
        min(edge, _float_param(params, "floor_shift_positive_cap")),
        _float_param(params, "floor_shift_negative_cap"),
    ) * reliability
    multiplier = 1.0 + max(
        min(edge * _float_param(params, "position_edge_weight"), _float_param(params, "position_edge_positive_cap")),
        _float_param(params, "position_edge_negative_cap"),
    ) * reliability
    return round(floor_shift, 2), round(multiplier, 4)


def _dynamic_params() -> dict:
    values = {**LOW_BUY_DYNAMIC_ADJUSTMENT_DEFAULTS, **get_low_buy_dynamic_adjustment()}
    return values


def _float_param(params: dict, key: str) -> float:
    return float(params.get(key, LOW_BUY_DYNAMIC_ADJUSTMENT_DEFAULTS[key]))


def _int_param(params: dict, key: str) -> int:
    return int(params.get(key, LOW_BUY_DYNAMIC_ADJUSTMENT_DEFAULTS[key]))
