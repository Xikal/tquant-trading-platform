from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.low_buy.production_scoring_config import (
    BASE_PRODUCTION_SCORE,
    BASE_WATCH_SCORE,
    CAPS,
    DEFAULT_SCORE_CAP,
    FRONT_ROW_INTERACTION_TIERS,
    FRONT_ROW_INTERACTION_WEIGHTS,
    FRONT_ROW_PRODUCTION_WEIGHTS,
    FRONT_ROW_WATCH_WEIGHTS,
    LAGGARD_TIERS,
    MARKET_PRODUCTION_WEIGHTS,
    MARKET_WATCH_WEIGHTS,
    PORTFOLIO_CANDIDATE_SCORE_THRESHOLD,
    PRODUCTION_SCORING_CONFIG_VERSION,
    PRODUCTION_SIGNAL_WEIGHTS,
    PRODUCTION_STRATEGY_PRIORS,
    RETREAT_MARKET_STATES,
    SHADOW_CONFIRM_SCORE_THRESHOLD,
    WATCH_SIGNAL_WEIGHTS,
    WATCH_STRATEGY_PRIORS,
    WEAK_MARKET_STATES,
)
from app.services.low_buy.strategy_policy import is_low_sample_capped_strategy, participates_in_priority_board


PRODUCTION_STATES = {"buy_now", "soft_buy_now"}


@dataclass(frozen=True)
class ProductionMarketContext:
    market_state: str = "unknown"
    market_state_text: str = ""
    hot_industries: tuple[str, ...] = ()
    industry_ranks: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class ProductionScoreResult:
    production_score: float | None
    watch_score: float | None
    decision: str
    front_row_tier: str
    score_cap: float | None
    score_components: dict[str, float]
    exclusion_reasons: list[str]
    warning_tags: list[str]
    config_version: str = PRODUCTION_SCORING_CONFIG_VERSION

    def as_payload(self) -> dict[str, Any]:
        return {
            "production_score": self.production_score,
            "watch_score": self.watch_score,
            "production_decision": self.decision,
            "front_row_tier": self.front_row_tier,
            "score_cap": self.score_cap,
            "score_components": dict(self.score_components),
            "exclusion_reasons": list(self.exclusion_reasons),
            "warning_tags": list(self.warning_tags),
            "production_scoring_config_version": self.config_version,
        }


def score_low_buy_candidate_for_production(
    candidate: Any,
    *,
    market_context: Any | None = None,
    portfolio_context: Any | None = None,
    mode: str = "shadow",
) -> ProductionScoreResult:
    del portfolio_context, mode
    signal_state = _text_attr(candidate, "buy_signal_state", "watch")
    strategy_key = _text_attr(candidate, "strategy_key", "")
    market_state = _market_state(candidate, market_context)
    front_row_tier = resolve_front_row_tier(candidate, market_context=market_context)

    components: dict[str, float] = {}
    warnings = ["front_row_weighted_shadow"]
    exclusions: list[str] = []
    score_cap: float | None = DEFAULT_SCORE_CAP

    hard_risk_reasons = _hard_risk_reasons(candidate)
    if hard_risk_reasons:
        exclusions.extend(hard_risk_reasons)

    if _extreme_laggard_blocked(candidate, market_state, front_row_tier):
        exclusions.append("extreme_laggard_blocked")

    watch_score = _watch_score(
        candidate=candidate,
        signal_state=signal_state,
        strategy_key=strategy_key,
        market_state=market_state,
        front_row_tier=front_row_tier,
    )

    if exclusions:
        return ProductionScoreResult(
            production_score=None,
            watch_score=watch_score,
            decision="excluded",
            front_row_tier=front_row_tier,
            score_cap=None,
            score_components={},
            exclusion_reasons=_dedupe(exclusions),
            warning_tags=_dedupe(warnings + ["hard_risk_excluded"]),
        )

    production_weight = PRODUCTION_SIGNAL_WEIGHTS.get(signal_state)
    if production_weight is None or signal_state not in PRODUCTION_STATES:
        if signal_state == "near_entry":
            warnings.append("near_entry_watch_only")
        return ProductionScoreResult(
            production_score=None,
            watch_score=watch_score,
            decision="watch_only",
            front_row_tier=front_row_tier,
            score_cap=None,
            score_components={},
            exclusion_reasons=[],
            warning_tags=_dedupe(warnings),
        )

    if not participates_in_priority_board(strategy_key):
        warnings.append("non_production_strategy")
        return ProductionScoreResult(
            production_score=None,
            watch_score=watch_score,
            decision="research_watch_only",
            front_row_tier=front_row_tier,
            score_cap=CAPS.non_production_strategy,
            score_components={},
            exclusion_reasons=["non_production_strategy"],
            warning_tags=_dedupe(warnings),
        )

    components["base"] = BASE_PRODUCTION_SCORE
    components["signal_state"] = float(production_weight)
    components["strategy_prior"] = PRODUCTION_STRATEGY_PRIORS.get(strategy_key, 0.0)
    components["front_row_strength"] = FRONT_ROW_PRODUCTION_WEIGHTS.get(front_row_tier, FRONT_ROW_PRODUCTION_WEIGHTS["unknown"])
    components["strategy_front_interaction"] = _front_row_interaction(strategy_key, front_row_tier)
    components["market_state"] = MARKET_PRODUCTION_WEIGHTS.get(market_state, MARKET_PRODUCTION_WEIGHTS["unknown"])
    components["entry_structure"] = _entry_structure_score(candidate, signal_state=signal_state, production=True)
    components["risk_quality"] = _risk_quality_score(candidate)
    components["external_factor"] = _external_factor_score(candidate)
    components["laggard_penalty"] = _laggard_penalty(front_row_tier)
    components["retreat_penalty"] = -6.0 if market_state in RETREAT_MARKET_STATES and front_row_tier in LAGGARD_TIERS else 0.0
    components["abnormal_penalty"] = _abnormal_penalty(candidate)

    score_cap = _score_cap(strategy_key=strategy_key, market_state=market_state, front_row_tier=front_row_tier)
    raw_score = sum(components.values())
    production_score = round(max(0.0, min(float(score_cap), raw_score)), 2)
    decision = _decision(production_score, market_state=market_state)
    if front_row_tier in LAGGARD_TIERS:
        warnings.append("laggard_capped")
    if is_low_sample_capped_strategy(strategy_key):
        warnings.append("low_sample_capped")
    if market_state in RETREAT_MARKET_STATES:
        warnings.append("retreat_market_no_new_position")
    elif market_state in WEAK_MARKET_STATES and front_row_tier in LAGGARD_TIERS:
        warnings.append("weak_market_laggard_capped")
    return ProductionScoreResult(
        production_score=production_score,
        watch_score=watch_score,
        decision=decision,
        front_row_tier=front_row_tier,
        score_cap=score_cap,
        score_components={key: round(value, 4) for key, value in components.items() if value},
        exclusion_reasons=[],
        warning_tags=_dedupe(warnings),
    )


def resolve_front_row_tier(candidate: Any, *, market_context: Any | None = None) -> str:
    leader_rank = _text_attr(candidate, "leader_rank", "unknown")
    mainline_tier = _text_attr(candidate, "mainline_tier", "unknown")
    industry_tier = _text_attr(candidate, "industry_tier", "neutral")
    leader_strength_rank = _int_attr(candidate, "leader_strength_rank", 0)
    leader_strength_score = _float_attr(candidate, "leader_strength_score", 0.0)
    industry_rank = _industry_rank(candidate, market_context)

    if (
        leader_rank in {"leader", "strong_follow"}
        and mainline_tier == "core_mainline"
        and (
            0 < leader_strength_rank <= 3
            or leader_strength_score >= 70.0
            or industry_rank in {1, 2, 3}
        )
    ):
        return "core_leader"
    if leader_rank in {"leader", "strong_follow"} and (
        industry_tier in {"core_hot", "secondary_hot"}
        or mainline_tier in {"core_mainline", "secondary_mainline"}
    ):
        return "leader_hot"
    if leader_rank == "strong_follow" or (0 < leader_strength_rank <= 8 and leader_strength_score >= 55.0):
        return "strong_follower"
    if leader_rank == "laggard" and industry_tier in {"cold", "cold_laggard"}:
        return "cold_laggard"
    if leader_rank == "laggard":
        return "laggard"
    if industry_tier in {"neutral", "rotation", "rotation_hot"}:
        return "middle"
    return "unknown"


def production_score_payload(candidate: Any, *, market_context: Any | None = None) -> dict[str, Any]:
    return score_low_buy_candidate_for_production(candidate, market_context=market_context).as_payload()


def _watch_score(
    *,
    candidate: Any,
    signal_state: str,
    strategy_key: str,
    market_state: str,
    front_row_tier: str,
) -> float:
    score = BASE_WATCH_SCORE
    score += WATCH_SIGNAL_WEIGHTS.get(signal_state, 0.0)
    score += WATCH_STRATEGY_PRIORS.get(strategy_key, 0.0)
    score += FRONT_ROW_WATCH_WEIGHTS.get(front_row_tier, 0.0)
    score += MARKET_WATCH_WEIGHTS.get(market_state, 0.0)
    score += _entry_structure_score(candidate, signal_state=signal_state, production=False)
    score -= max(0.0, _float_attr(candidate, "distribution_risk_score", 0.0) - 4.0) * 1.6
    score += _external_factor_score(candidate) * 0.5
    score += _abnormal_penalty(candidate)
    return round(max(0.0, min(100.0, score)), 2)


def _market_state(candidate: Any, market_context: Any | None) -> str:
    value = _text_from_context(market_context, "market_state")
    if value:
        return value
    return _text_attr(candidate, "market_state", _text_attr(candidate, "market_state_category", "unknown")) or "unknown"


def _score_cap(*, strategy_key: str, market_state: str, front_row_tier: str) -> float:
    cap = DEFAULT_SCORE_CAP
    if front_row_tier in LAGGARD_TIERS:
        cap = min(cap, CAPS.laggard)
    if market_state in WEAK_MARKET_STATES and front_row_tier in LAGGARD_TIERS:
        cap = min(cap, CAPS.weak_market_laggard)
    if market_state in RETREAT_MARKET_STATES:
        cap = min(cap, CAPS.retreat_market)
    if is_low_sample_capped_strategy(strategy_key):
        cap = min(cap, CAPS.low_sample_strategy)
    return float(cap)


def _front_row_interaction(strategy_key: str, front_row_tier: str) -> float:
    if front_row_tier not in FRONT_ROW_INTERACTION_TIERS:
        return 0.0
    return FRONT_ROW_INTERACTION_WEIGHTS.get(strategy_key, 0.0)


def _entry_structure_score(candidate: Any, *, signal_state: str, production: bool) -> float:
    distance = _float_attr(candidate, "entry_distance_pct", 0.0)
    execution_ready = bool(getattr(candidate, "execution_ready", False))
    if signal_state == "near_entry":
        return 0.0 if production else 8.0
    if execution_ready and abs(distance) <= 0.8:
        return 8.0 if production else 6.0
    if 0.8 < distance <= 2.0:
        return 4.0 if production else 5.0
    if distance < -1.5:
        return -4.0 if production else 2.0
    return 0.0


def _risk_quality_score(candidate: Any) -> float:
    risk_tier = _text_attr(candidate, "risk_tier", "note")
    distribution = _float_attr(candidate, "distribution_risk_score", 0.0)
    if risk_tier == "degrade" or distribution >= 5.8:
        return -12.0
    if distribution >= 4.2:
        return -6.0
    if _text_attr(candidate, "data_quality", "ok") not in {"ok", "fresh", "complete"}:
        return -15.0
    if distribution <= 2.5 and _float_attr(candidate, "stop_loss", 0.0) > 0:
        return 6.0
    return 2.0


def _external_factor_score(candidate: Any) -> float:
    value = min(max(_float_attr(candidate, "multi_timeframe_resonance_score", 0.0), 0.0), 6.0)
    main_force = getattr(candidate, "main_force_advice", {}) or {}
    if isinstance(main_force, dict):
        action = str(main_force.get("action") or main_force.get("main_force_action") or "")
        if action in {"buy_confirmed", "accumulate", "strong_accumulate"}:
            value += 2.0
        elif action in {"sell", "distribution", "avoid"}:
            value -= 3.0
    return round(value, 4)


def _laggard_penalty(front_row_tier: str) -> float:
    if front_row_tier == "laggard":
        return -4.0
    if front_row_tier == "cold_laggard":
        return -8.0
    return 0.0


def _abnormal_penalty(candidate: Any) -> float:
    penalty = 0.0
    if bool(getattr(candidate, "false_breakout_flag", False)):
        penalty -= 10.0
    if bool(getattr(candidate, "intraday_reversal_flag", False)):
        penalty -= 10.0
    if bool(getattr(candidate, "stall_after_volume_flag", False)):
        penalty -= 4.0
    return penalty


def _hard_risk_reasons(candidate: Any) -> list[str]:
    reasons: list[str] = []
    hard_risk = getattr(candidate, "hard_risk", None)
    if bool(getattr(hard_risk, "execution_blocked", False)):
        reasons.extend([str(item) for item in getattr(hard_risk, "reasons", []) if str(item or "").strip()])
        reasons.append("hard_risk_execution_blocked")
    if _text_attr(candidate, "risk_tier", "") == "block":
        reasons.append("risk_tier_block")
    if _text_attr(candidate, "data_quality", "ok") in {"missing", "invalid", "stale_block", "future_leak"}:
        reasons.append("data_quality_hard_risk")
    if _float_attr(candidate, "latest_price", 0.0) <= 0:
        reasons.append("invalid_price")
    if _float_attr(candidate, "distribution_risk_score", 0.0) >= 8.6:
        reasons.append("distribution_hard_risk")
    name = _text_attr(candidate, "name", "")
    if "ST" in name.upper() or "*ST" in name.upper() or "退" in name:
        reasons.append("name_hard_risk")
    return _dedupe(reasons)


def _extreme_laggard_blocked(candidate: Any, market_state: str, front_row_tier: str) -> bool:
    if front_row_tier == "cold_laggard" and market_state in WEAK_MARKET_STATES | RETREAT_MARKET_STATES:
        return True
    if market_state in RETREAT_MARKET_STATES and front_row_tier in LAGGARD_TIERS:
        return True
    if bool(getattr(candidate, "intraday_reversal_flag", False)) and _float_attr(candidate, "distribution_risk_score", 0.0) >= 5.8:
        return True
    return False


def _decision(score: float, *, market_state: str) -> str:
    if market_state in RETREAT_MARKET_STATES:
        return "watch_only_retreat_market"
    if score >= PORTFOLIO_CANDIDATE_SCORE_THRESHOLD:
        return "portfolio_candidate"
    if score >= SHADOW_CONFIRM_SCORE_THRESHOLD:
        return "shadow_confirm"
    if score >= 60.0:
        return "watch_only"
    return "avoid"


def _industry_rank(candidate: Any, market_context: Any | None) -> int:
    industry = _text_attr(candidate, "sector_name", "")
    ranks = getattr(market_context, "industry_ranks", None)
    if isinstance(ranks, dict) and industry:
        try:
            return int(ranks.get(industry, 0) or 0)
        except (TypeError, ValueError):
            return 0
    return 0


def _text_from_context(context: Any | None, field_name: str) -> str:
    if context is None:
        return ""
    if isinstance(context, dict):
        return str(context.get(field_name) or "").strip()
    return str(getattr(context, field_name, "") or "").strip()


def _text_attr(candidate: Any, field_name: str, default: str = "") -> str:
    return str(getattr(candidate, field_name, default) or default).strip()


def _float_attr(candidate: Any, field_name: str, default: float = 0.0) -> float:
    try:
        return float(getattr(candidate, field_name, default) or default)
    except (TypeError, ValueError):
        return default


def _int_attr(candidate: Any, field_name: str, default: int = 0) -> int:
    try:
        return int(getattr(candidate, field_name, default) or default)
    except (TypeError, ValueError):
        return default


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = str(value or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(key)
    return result
