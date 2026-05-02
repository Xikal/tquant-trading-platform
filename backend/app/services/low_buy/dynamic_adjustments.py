from __future__ import annotations

from dataclasses import dataclass

from app.models.schemas import LowBuyCandidateOut, LowBuyStrategyPerformanceOut
from app.services.market.regime import MarketRegimeSnapshot
from app.services.low_buy.shared import LOW_BUY_THRESHOLDS


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
    floor_shift = _market_floor_shift(state)
    position_multiplier = 1.0
    reason_parts = [f"环境 {state}"]

    if risk_tier == "block":
        floor_shift += 99.0
        reason_parts.append("风险阻断")
    elif risk_tier == "degrade":
        floor_shift += 2.4
        reason_parts.append("风险降级")

    if leader_rank == "leader":
        floor_shift -= 0.7
        position_multiplier *= 1.04
        reason_parts.append("主线龙头加权")
    elif leader_rank == "laggard":
        floor_shift += 1.0
        position_multiplier *= 0.88
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
        floor_shift -= min(factor_bonus * 0.16, 0.8)
        reason_parts.append(f"因子加分 +{factor_bonus:.1f}")

    return LowBuyDynamicAdjustment(
        score_floor_shift=round(max(-2.0, min(99.0, floor_shift)), 2),
        soft_buy_threshold_shift=round(max(-1.5, min(6.0, floor_shift * 0.55)), 2),
        position_multiplier=round(max(0.0, min(1.2, position_multiplier)), 4),
        reason=" · ".join(reason_parts),
    )


def apply_performance_adjustment_to_candidate(
    candidate: LowBuyCandidateOut,
    performance: LowBuyStrategyPerformanceOut | None,
) -> LowBuyCandidateOut:
    if performance is None or performance.filled_signals < 50:
        return candidate
    _, position_multiplier = _performance_adjustment(performance)
    return candidate.model_copy(
        update={
            "dynamic_position_multiplier": round(candidate.dynamic_position_multiplier * position_multiplier, 4),
        }
    )


def _market_floor_shift(state: str) -> float:
    return {
        "broad_rally": -1.2,
        "repair": -0.4,
        "weight_support_active": 0.6,
        "low_volume_wait": 1.0,
        "fast_rotation": 1.8,
        "weight_support": 2.2,
        "high_flyer_retreat": 3.2,
        "risk_release": 5.0,
    }.get(state, 1.0)


def _performance_adjustment(performance: LowBuyStrategyPerformanceOut) -> tuple[float, float]:
    filled = max(performance.filled_signals, 0)
    if filled < 50:
        return 0.0, 1.0
    reliability = min(1.0, (filled - 50) / 50.0)
    if reliability <= 0:
        return 0.0, 1.0
    edge = performance.net_win_rate * 0.0175 + performance.avg_net_return_pct * 0.08
    if performance.avg_max_drawdown_5d < -6.0:
        edge -= 0.8
    floor_shift = -max(min(edge, 2.2), -2.8) * reliability
    multiplier = 1.0 + max(min(edge * 0.035, 0.12), -0.18) * reliability
    return round(floor_shift, 2), round(multiplier, 4)
