from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.models.schemas import LowBuyCandidateOut


MarketGuardMode = Literal["none", "degrade_retreat", "block_retreat"]
GuardTargetState = Literal["near_entry", "watch", "avoid"]

ACTIONABLE_SIGNAL_STATES = frozenset({"buy_now", "soft_buy_now"})
DEFAULT_RETREAT_STATES = ("high_flyer_retreat", "risk_release")


@dataclass(frozen=True)
class MarketGuardOverride:
    """Research-only market-state guard used by backtest scripts.

    Production low-buy signal resolution already has market-state rules.  This
    guard exists so Q-006 can be A/B tested without changing live strategy truth.
    """

    mode: MarketGuardMode = "none"
    states: tuple[str, ...] = DEFAULT_RETREAT_STATES
    degrade_to: GuardTargetState = "near_entry"
    min_strength: float = 0.0


def apply_market_guard(
    candidate: LowBuyCandidateOut,
    guard: MarketGuardOverride | None,
) -> tuple[LowBuyCandidateOut, str]:
    if guard is None or guard.mode == "none":
        return candidate, ""
    signal_state = str(candidate.buy_signal_state or "")
    if signal_state not in ACTIONABLE_SIGNAL_STATES:
        return candidate, ""
    market_state = str(candidate.market_state or "")
    if market_state not in set(guard.states):
        return candidate, ""
    strength = _float_value(candidate.market_state_strength)
    if strength < float(guard.min_strength or 0.0):
        return candidate, ""

    target_state: GuardTargetState = "avoid" if guard.mode == "block_retreat" else guard.degrade_to
    if target_state == signal_state:
        return candidate, ""
    reason = f"{guard.mode}:{market_state}:{signal_state}->{target_state}"
    return _guarded_candidate(candidate, target_state=target_state, reason=reason), reason


def market_guard_label(guard: MarketGuardOverride | None) -> str:
    if guard is None or guard.mode == "none":
        return "none"
    target = "avoid" if guard.mode == "block_retreat" else guard.degrade_to
    states = "|".join(guard.states)
    return f"{guard.mode}: states={states}, min_strength={guard.min_strength:g}, target={target}"


def market_guard_stem(guard: MarketGuardOverride | None) -> str:
    if guard is None or guard.mode == "none":
        return "no_guard"
    target = "avoid" if guard.mode == "block_retreat" else guard.degrade_to
    state_part = "-".join(_stem_text(item) for item in guard.states)
    return f"guard_{guard.mode}_{state_part}_to_{target}_min_{_stem_number(guard.min_strength)}"


def _guarded_candidate(
    candidate: LowBuyCandidateOut,
    *,
    target_state: GuardTargetState,
    reason: str,
) -> LowBuyCandidateOut:
    market_text = candidate.market_state_text or candidate.market_state or "市场退潮"
    action_text = "研究态退潮阻断" if target_state == "avoid" else "研究态退潮降级"
    hint = (
        f"研究回测市场保护：{market_text} 触发退潮/高位分化保护，"
        f"原 {candidate.buy_signal_state} 降级为 {target_state}；该结果只用于 A/B 验证。"
    )
    return candidate.model_copy(
        update={
            "buy_signal_state": target_state,
            "buy_signal_text": action_text,
            "buy_signal_hint": hint,
            "execution_ready": False,
            "execution_note": "研究态市场保护已阻断新开仓。",
            "risks": [*list(candidate.risks or []), hint],
            "tags": [*list(candidate.tags or []), "研究态市场保护", reason],
        }
    )


def _float_value(value) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _stem_number(value: float) -> str:
    return f"{float(value):g}".replace("-", "m").replace(".", "p")


def _stem_text(value: str) -> str:
    return str(value or "unknown").strip().replace("/", "_").replace(" ", "_")
