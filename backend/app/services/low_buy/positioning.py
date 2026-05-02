from __future__ import annotations

from app.models.schemas import LowBuyCandidateOut


def total_position_multiplier(candidate: LowBuyCandidateOut) -> float:
    return round(
        max(candidate.market_position_multiplier, 0.0)
        * max(candidate.risk_position_multiplier, 0.0)
        * max(candidate.industry_position_multiplier, 0.0)
        * max(candidate.dynamic_position_multiplier, 0.0),
        4,
    )


def build_position_breakdown_text(candidate: LowBuyCandidateOut, position_pct: float) -> str:
    if position_pct <= 0:
        return ""
    return (
        f"环境 {candidate.market_position_multiplier:.2f} × "
        f"风险 {candidate.risk_position_multiplier:.2f} × "
        f"行业 {candidate.industry_position_multiplier:.2f} × "
        f"动态 {candidate.dynamic_position_multiplier:.2f} = {position_pct:.1f}%"
    )
