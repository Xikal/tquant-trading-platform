from __future__ import annotations

from dataclasses import dataclass

from app.services.low_buy.candidate_types import CandidateMetrics
from app.services.market.regime import MarketRegimeSnapshot


@dataclass(frozen=True)
class LowBuyRiskTierDecision:
    risk_tier: str
    score_penalty: float
    position_multiplier: float
    execution_blocked: bool
    risks: list[str]
    tags: list[str]


STRICT_STRATEGIES = {
    "first_board",
    "volume_shrink",
    "late_session_strong_support",
    "core_midcap_vwap_ma5_retrace",
    "sector_mainline_first_divergence_low_buy",
    "mainline_limitup_shrink_retrace_reclaim",
    "trend_rebound",
    "deep_pullback",
    "limit_up_breakout_retrace",
    "divergence_consensus",
}
STRUCTURE_STRATEGIES = {"classic_retrace", "ma_support", "breakout_support"}


def resolve_low_buy_risk_tier(
    *,
    strategy: str,
    metrics: CandidateMetrics,
    market_regime: MarketRegimeSnapshot | None,
) -> LowBuyRiskTierDecision:
    risks: list[str] = []
    tags: list[str] = []
    state = market_regime.state if market_regime is not None else "low_volume_wait"
    score = _risk_score(strategy, metrics, state)
    if metrics.false_breakout_flag:
        risks.append("最近一次冲高后重新跌回关键突破位下方，存在明显假突破风险。")
        tags.append("假突破风险")
    if metrics.stall_after_volume_flag:
        risks.append("放量后价格扩张变差，存在边拉边派发的滞涨迹象。")
        tags.append("放量滞涨")
    if metrics.intraday_reversal_flag:
        risks.append("日K 收在相对弱位，冲高回落后承接偏弱。")
        tags.append("冲高回落")

    if _should_block(strategy, metrics, state, score):
        return LowBuyRiskTierDecision(
            risk_tier="block",
            score_penalty=4.2,
            position_multiplier=0.0,
            execution_blocked=True,
            risks=risks + ["风险分层为阻断级：即使价格到位，也必须等待重新修复后再评估。"],
            tags=tags + ["风险阻断"],
        )
    if score >= 5.2:
        return LowBuyRiskTierDecision(
            risk_tier="degrade",
            score_penalty=2.1,
            position_multiplier=0.62,
            execution_blocked=False,
            risks=risks + ["风险分层为降级级：只允许更轻仓位和更强确认。"],
            tags=tags + ["风险降级"],
        )
    return LowBuyRiskTierDecision(
        risk_tier="note",
        score_penalty=0.4 if score >= 3.2 else 0.0,
        position_multiplier=0.90 if score >= 3.2 else 1.0,
        execution_blocked=False,
        risks=risks,
        tags=tags + (["风险提示"] if score >= 3.2 else []),
    )


def _risk_score(strategy: str, metrics: CandidateMetrics, market_state: str) -> float:
    score = metrics.distribution_risk_score * (0.52 if strategy in STRUCTURE_STRATEGIES else 0.68)
    if metrics.false_breakout_flag:
        score += 2.4 if strategy in STRICT_STRATEGIES else 1.4
    if metrics.stall_after_volume_flag:
        score += 1.3
    if metrics.intraday_reversal_flag:
        score += 1.1
    if market_state in {"high_flyer_retreat", "risk_release"}:
        score += 1.4
    elif market_state in {"fast_rotation", "weight_support"}:
        score += 0.7
    return score


def _should_block(strategy: str, metrics: CandidateMetrics, market_state: str, score: float) -> bool:
    if strategy == "limit_up_breakout_retrace" and metrics.false_breakout_flag:
        return True
    if strategy == "divergence_consensus" and (
        metrics.false_breakout_flag
        or metrics.intraday_reversal_flag
        or metrics.stall_after_volume_flag
    ):
        return True
    if strategy in STRICT_STRATEGIES and metrics.false_breakout_flag and score >= 5.5:
        return True
    if metrics.distribution_risk_score >= (8.6 if strategy in STRUCTURE_STRATEGIES else 7.1):
        return True
    if market_state == "risk_release" and metrics.distribution_risk_score >= 5.0:
        return True
    if market_state == "high_flyer_retreat" and strategy in STRICT_STRATEGIES and score >= 6.0:
        return True
    return False
