from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.ml_signal.promotion_quality import binomial_accuracy_p_value


PHASE1_MIN_FILLED_SIGNALS = 30
PHASE3_MIN_FILLED_SIGNALS = 50
PHASE3_MIN_AVG_NET_RETURN_PCT = 0.3
PHASE3_MIN_HEALTH_SCORE = 60.0
PHASE3_MAX_BINOMIAL_P_VALUE = 0.15


@dataclass(frozen=True)
class StrategyValidationPhase:
    phase: str
    phase_text: str
    reason: str
    position_scale: float


def resolve_strategy_validation_phase(performance: Any, health_score: float) -> StrategyValidationPhase:
    filled = int(getattr(performance, "filled_signals", 0) or 0)
    win_rate = float(getattr(performance, "hit_rate", 0.0) or 0.0)
    avg_net = float(getattr(performance, "avg_net_return_pct", 0.0) or 0.0)
    hit_count = _resolve_hit_count(performance, filled, win_rate)
    p_value = binomial_accuracy_p_value(hit_count, filled, baseline=0.5) if filled > 0 else 1.0
    if filled < PHASE1_MIN_FILLED_SIGNALS:
        return StrategyValidationPhase(
            "phase1_shadow",
            "Phase 1 影子观察",
            f"真实成交样本 {filled}/{PHASE1_MIN_FILLED_SIGNALS}，只记录信号，不放大仓位。",
            0.0,
        )
    if filled < PHASE3_MIN_FILLED_SIGNALS:
        return StrategyValidationPhase(
            "phase2_small",
            "Phase 2 小仓验证",
            f"样本 {filled}/{PHASE3_MIN_FILLED_SIGNALS}，仅允许小仓验证。",
            0.2,
        )
    if avg_net < PHASE3_MIN_AVG_NET_RETURN_PCT:
        return StrategyValidationPhase(
            "phase2_small",
            "Phase 2 小仓验证",
            f"均净收益 {avg_net:.2f}%/{PHASE3_MIN_AVG_NET_RETURN_PCT:.2f}% 未达全仓执行门槛。",
            0.2,
        )
    if p_value > PHASE3_MAX_BINOMIAL_P_VALUE:
        return StrategyValidationPhase(
            "phase2_small",
            "Phase 2 小仓验证",
            f"胜率 {win_rate:.1f}% 的二项检验 p={p_value:.3f}，未显著优于随机基准。",
            0.2,
        )
    if health_score < PHASE3_MIN_HEALTH_SCORE:
        return StrategyValidationPhase(
            "phase2_small",
            "Phase 2 小仓验证",
            f"健康分 {health_score:.1f}/{PHASE3_MIN_HEALTH_SCORE:.0f} 未达全仓执行门槛。",
            0.2,
        )
    return StrategyValidationPhase(
        "phase3_full",
        "Phase 3 标准执行",
        f"样本 {filled}、胜率 {win_rate:.1f}%、p={p_value:.3f}、健康分 {health_score:.1f} 达到标准执行门槛。",
        1.0,
    )


def _resolve_hit_count(performance: Any, filled: int, win_rate: float) -> int:
    raw_hit_count = getattr(performance, "hit_count", None)
    if raw_hit_count is not None:
        try:
            return max(0, min(filled, int(raw_hit_count)))
        except (TypeError, ValueError):
            pass
    return max(0, min(filled, round(filled * win_rate / 100.0)))
