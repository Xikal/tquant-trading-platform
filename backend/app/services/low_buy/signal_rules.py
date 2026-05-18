from __future__ import annotations

from typing import Callable

from app.services.low_buy.candidate_observation_confirmation import N_PATTERN_CONFIRMATION_STRATEGIES
from app.services.low_buy.market_state_rules import hard_buy_allowed, resolve_strategy_market_profile, soft_buy_allowed
from app.services.low_buy.shared import LowBuyCandidateOut
from app.services.low_buy.strategy_policy import strategy_layer, strong_buy_paused


def can_hard_buy_now(
    *,
    candidate: LowBuyCandidateOut,
    entry_position: str,
    hard_confirmed: bool,
    auto_governance_blocks_buy: Callable[[LowBuyCandidateOut], bool],
    weak_market_thematic_block_reason: Callable[[LowBuyCandidateOut], str],
    has_distribution_hard_block: Callable[[LowBuyCandidateOut], bool],
    strategy_hard_buy_quality_gate: Callable[[LowBuyCandidateOut], bool],
    hard_buy_min_score: Callable[[LowBuyCandidateOut], float],
    is_strict_in_zone_strategy: Callable[[str], bool],
    below_zone_hard_buy_allowed: Callable[[LowBuyCandidateOut], bool],
) -> bool:
    if strong_buy_paused(candidate.strategy_key):
        return False
    if auto_governance_blocks_buy(candidate):
        return False
    if not candidate.execution_ready:
        return False
    if candidate.risk_tier == "block":
        return False
    morphology_only = candidate.strategy_key in N_PATTERN_CONFIRMATION_STRATEGIES
    if not morphology_only and weak_market_thematic_block_reason(candidate):
        return False
    if not morphology_only and not hard_buy_allowed(
        candidate.strategy_key,
        candidate.market_state,
        candidate.market_state_strength,
    ):
        return False
    if has_distribution_hard_block(candidate):
        return False
    if not strategy_hard_buy_quality_gate(candidate):
        return False
    if candidate.score < hard_buy_min_score(candidate):
        return False
    if is_strict_in_zone_strategy(candidate.strategy_key):
        return entry_position == "in_zone" and hard_confirmed
    if entry_position == "in_zone":
        return hard_confirmed
    if entry_position == "below_zone":
        return hard_confirmed and below_zone_hard_buy_allowed(candidate)
    return False


def can_soft_buy_now(
    *,
    candidate: LowBuyCandidateOut,
    entry_position: str,
    soft_confirmed: bool,
    auto_governance_blocks_buy: Callable[[LowBuyCandidateOut], bool],
    weak_market_thematic_block_reason: Callable[[LowBuyCandidateOut], str],
    has_distribution_soft_block: Callable[[LowBuyCandidateOut], bool],
    strategy_soft_buy_quality_gate: Callable[[LowBuyCandidateOut], bool],
    soft_buy_min_score: Callable[[str, str, float], float],
    is_strict_in_zone_strategy: Callable[[str], bool],
    near_above_soft_buy_allowed: Callable[[LowBuyCandidateOut], bool],
) -> bool:
    if strong_buy_paused(candidate.strategy_key):
        return False
    if auto_governance_blocks_buy(candidate):
        return False
    if not candidate.execution_ready or not soft_confirmed:
        return False
    if candidate.risk_tier == "block":
        return False
    morphology_only = candidate.strategy_key in N_PATTERN_CONFIRMATION_STRATEGIES
    if not morphology_only and weak_market_thematic_block_reason(candidate):
        return False
    if not morphology_only and not soft_buy_allowed(
        candidate.strategy_key,
        candidate.market_state,
        candidate.market_state_strength,
    ):
        return False
    if has_distribution_soft_block(candidate):
        return False
    if not strategy_soft_buy_quality_gate(candidate):
        return False
    min_score = soft_buy_min_score(
        candidate.strategy_key,
        entry_position,
        candidate.dynamic_threshold_adjustment,
    )
    if is_strict_in_zone_strategy(candidate.strategy_key):
        return entry_position == "in_zone" and candidate.score >= min_score
    if entry_position == "in_zone":
        return candidate.score >= min_score
    if entry_position == "near_above_zone":
        return near_above_soft_buy_allowed(candidate) and candidate.score >= min_score
    return False


def market_block_can_keep_research(candidate: LowBuyCandidateOut) -> bool:
    return (
        strategy_layer(candidate.strategy_key) == "research"
        and candidate.risk_tier != "block"
        and not candidate.false_breakout_flag
        and not candidate.intraday_reversal_flag
        and candidate.distribution_risk_score < 6.5
    )


def signal_block_hint(
    *,
    candidate: LowBuyCandidateOut,
    auto_override: dict | None,
    weak_market_thematic_block_reason: Callable[[LowBuyCandidateOut], str],
) -> str:
    if auto_override:
        status = str(auto_override.get("status") or "")
        reason = str(auto_override.get("reason") or "")
        if status == "paused":
            return reason or "策略绩效自动治理已暂停该策略强信号。"
        if status == "watch" and candidate.buy_signal_state in {"buy_now", "soft_buy_now"}:
            return reason or "策略绩效自动治理已将该策略降级为观察。"
    if candidate.risk_tier == "block":
        return "风险分层已触发阻断，即使价格到位也不执行。"
    if candidate.strategy_key in N_PATTERN_CONFIRMATION_STRATEGIES:
        return ""
    profile = resolve_strategy_market_profile(
        candidate.strategy_key,
        candidate.market_state,
        candidate.market_state_strength,
    )
    if profile.execution_blocked:
        if market_block_can_keep_research(candidate):
            return ""
        return f"当前{candidate.market_state_text or '市场环境'}明确阻断这类策略执行，先放弃本轮。"
    weak_market_reason = weak_market_thematic_block_reason(candidate)
    if weak_market_reason:
        if market_block_can_keep_research(candidate):
            return ""
        return weak_market_reason
    return ""


def can_show_research_near_entry(candidate: LowBuyCandidateOut, entry_position: str) -> bool:
    if strategy_layer(candidate.strategy_key) != "research":
        return False
    if candidate.research_stage not in {"near_entry", "buy_ready"}:
        return False
    if candidate.risk_tier == "block" or candidate.false_breakout_flag:
        return False
    if candidate.distribution_risk_score >= 6.5:
        return False
    if candidate.strategy_key == "divergence_consensus":
        return entry_position in {"in_zone", "near_above_zone"}
    return entry_position in {"in_zone", "near_above_zone", "below_zone"}


def research_near_entry_hint(candidate: LowBuyCandidateOut, entry_position: str) -> str:
    if candidate.research_stage == "buy_ready":
        return "研究策略确认条件基本满足，但当前仍暂停强买，只做接近买点提醒。"
    if candidate.strategy_key == "divergence_consensus":
        return "接近分歧高点确认位，等放量站稳且不冲高回落。"
    if entry_position == "below_zone":
        return "已回踩关键区下沿，必须快速收回支撑位才继续观察。"
    return "接近平台回踩关键位，等缩量承接和重新转强。"


def weak_market_thematic_block_reason(candidate: LowBuyCandidateOut) -> str:
    weak_states = {"fast_rotation", "high_flyer_retreat", "risk_release"}
    if candidate.market_state not in weak_states or candidate.instrument_type != "stock":
        return ""
    if candidate.market_state == "risk_release":
        return "风险释放期不新增题材股低吸，先等市场止跌和情绪修复。"
    is_mainline = candidate.leader_rank in {"leader", "strong_follow"} and candidate.industry_tier in {
        "core_hot",
        "secondary_hot",
    }
    if not is_mainline:
        return "轮动过快/高位退潮时，只保留主线龙头或强跟随的热点行业票。"
    if candidate.distribution_risk_score >= 5.2 or candidate.false_breakout_flag or candidate.intraday_reversal_flag:
        return "弱市场里只做分歧释放后的确认，当前派发或冲高回落风险未解除。"
    if candidate.market_state == "high_flyer_retreat" and candidate.strategy_key not in {
        "classic_retrace",
        "ma_support",
        "breakout_support",
    }:
        return "高位退潮期不做右侧突破、深回撤或后排结构，只保留主线支撑型低吸。"
    return ""
