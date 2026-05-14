from __future__ import annotations

from dataclasses import dataclass
from typing import Any


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
    if filled < 30:
        return StrategyValidationPhase(
            "phase1_shadow",
            "Phase 1 影子观察",
            f"真实成交样本 {filled}/30，只记录信号，不放大仓位。",
            0.0,
        )
    if filled < 50 or win_rate < 52.0 or avg_net < 0.3:
        return StrategyValidationPhase(
            "phase2_small",
            "Phase 2 小仓验证",
            f"样本 {filled}，胜率 {win_rate:.1f}%，均净收益 {avg_net:.2f}%，仅允许小仓验证。",
            0.2,
        )
    if health_score < 60:
        return StrategyValidationPhase(
            "phase2_small",
            "Phase 2 小仓验证",
            f"健康分 {health_score:.1f}/60 未达全仓执行门槛。",
            0.2,
        )
    return StrategyValidationPhase(
        "phase3_full",
        "Phase 3 标准执行",
        f"样本 {filled}、胜率 {win_rate:.1f}%、健康分 {health_score:.1f} 达到标准执行门槛。",
        1.0,
    )
