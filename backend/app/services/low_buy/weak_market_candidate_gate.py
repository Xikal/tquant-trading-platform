from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.low_buy.front_row_weighted_validation_config import (
    DEFAULT_WEAK_MARKET_POLICY,
    RETREAT_MARKET_STATES,
    WEAK_MARKET_POLICIES,
    WEAK_MARKET_STATES,
    WeakMarketPolicy,
)


@dataclass(frozen=True)
class WeakMarketGateResult:
    allowed_for_paper: bool
    demoted_to_watch: bool
    policy_name: str
    reason: str
    warning_tags: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "allowed_for_paper": self.allowed_for_paper,
            "demoted_to_watch": self.demoted_to_watch,
            "policy_name": self.policy_name,
            "reason": self.reason,
            "warning_tags": list(self.warning_tags),
        }


def resolve_weak_market_policy(name: str | None = None) -> WeakMarketPolicy:
    key = name or DEFAULT_WEAK_MARKET_POLICY
    if key not in WEAK_MARKET_POLICIES:
        raise ValueError(f"unknown weak market policy: {key}")
    return WEAK_MARKET_POLICIES[key]


def evaluate_weak_market_candidate(candidate: Any, *, policy_name: str | None = None) -> WeakMarketGateResult:
    policy = resolve_weak_market_policy(policy_name)
    market_state = _text(candidate, "market_state") or _text(candidate, "market_state_category")
    signal_state = _text(candidate, "buy_signal_state")
    front_row_tier = _text(candidate, "front_row_tier") or "unknown"
    score = _float(candidate, "production_score")
    if signal_state == "near_entry":
        return _blocked(policy.name, "near_entry_watch_only")
    if market_state in RETREAT_MARKET_STATES:
        return _blocked(policy.name, "retreat_market_no_new_position")
    if market_state not in WEAK_MARKET_STATES:
        return WeakMarketGateResult(True, False, policy.name, "non_weak_market", [])
    if not policy.allow_weak_market:
        return _blocked(policy.name, "weak_market_watch_only")
    if signal_state != "soft_buy_now" and policy.soft_buy_only:
        return _blocked(policy.name, "weak_market_buy_now_demoted")
    if score < policy.min_production_score:
        return _blocked(policy.name, "weak_market_score_below_policy")
    if front_row_tier not in policy.allowed_front_row_tiers:
        return _blocked(policy.name, "weak_market_front_row_tier_not_allowed")
    return WeakMarketGateResult(True, False, policy.name, "weak_market_policy_passed", ["weak_market_compressed"])


def filter_rows_for_weak_market_policy(rows: list[dict[str, Any]], *, policy_name: str) -> tuple[list[dict[str, Any]], dict[str, int]]:
    kept: list[dict[str, Any]] = []
    reasons: dict[str, int] = {}
    for row in rows:
        result = evaluate_weak_market_candidate(row, policy_name=policy_name)
        if result.allowed_for_paper:
            kept.append(row)
        else:
            reasons[result.reason] = reasons.get(result.reason, 0) + 1
    return kept, dict(sorted(reasons.items(), key=lambda item: (-item[1], item[0])))


def _blocked(policy_name: str, reason: str) -> WeakMarketGateResult:
    return WeakMarketGateResult(False, True, policy_name, reason, ["weak_market_compressed"])


def _text(candidate: Any, key: str) -> str:
    if isinstance(candidate, dict):
        return str(candidate.get(key) or "")
    return str(getattr(candidate, key, "") or "")


def _float(candidate: Any, key: str) -> float:
    value = candidate.get(key) if isinstance(candidate, dict) else getattr(candidate, key, 0.0)
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
