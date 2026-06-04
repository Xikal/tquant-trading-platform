from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


GateDecision = Literal["allow_production", "watch_only", "research_only", "blocked"]
PRODUCTION_SIGNAL_STATES = {"buy_now", "soft_buy_now"}
WATCH_ONLY_SIGNAL_STATES = {"near_entry", "watch", "observe_confirmed"}


@dataclass(frozen=True)
class StrategyGateInput:
    strategy_key: str
    signal_state: str = "watch"
    participates_in_priority_board: bool = False
    research_only: bool = False
    watch_only: bool = False
    shadow_paper: bool = False
    front_row_only: bool = False
    blocked: bool = False
    reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class StrategyExecutionGate:
    decision: GateDecision
    production_allowed: bool
    priority_board_allowed: bool
    production_score_allowed: bool
    reasons: list[str] = field(default_factory=list)
    warning_tags: list[str] = field(default_factory=list)

    def as_payload(self) -> dict[str, object]:
        return {
            "decision": self.decision,
            "production_allowed": self.production_allowed,
            "priority_board_allowed": self.priority_board_allowed,
            "production_score_allowed": self.production_score_allowed,
            "reasons": list(self.reasons),
            "warning_tags": list(self.warning_tags),
        }


def evaluate_strategy_gate(payload: StrategyGateInput) -> StrategyExecutionGate:
    reasons = _dedupe(payload.reasons)
    warnings: list[str] = []
    signal_state = str(payload.signal_state or "watch")

    if payload.blocked:
        return StrategyExecutionGate(
            decision="blocked",
            production_allowed=False,
            priority_board_allowed=False,
            production_score_allowed=False,
            reasons=_dedupe([*reasons, "blocked"]),
            warning_tags=["strategy_blocked"],
        )

    if payload.research_only:
        return StrategyExecutionGate(
            decision="research_only",
            production_allowed=False,
            priority_board_allowed=False,
            production_score_allowed=False,
            reasons=_dedupe([*reasons, "research_only"]),
            warning_tags=["research_only"],
        )

    if payload.watch_only or payload.shadow_paper or payload.front_row_only:
        if payload.watch_only:
            reasons.append("watch_only")
        if payload.shadow_paper:
            reasons.append("shadow_paper_only")
        if payload.front_row_only:
            reasons.append("front_row_only_watch")
        return StrategyExecutionGate(
            decision="watch_only",
            production_allowed=False,
            priority_board_allowed=False,
            production_score_allowed=False,
            reasons=_dedupe(reasons),
            warning_tags=["watch_only"],
        )

    if signal_state not in PRODUCTION_SIGNAL_STATES:
        if signal_state == "near_entry":
            warnings.append("near_entry_watch_only")
        elif signal_state in WATCH_ONLY_SIGNAL_STATES:
            warnings.append("signal_state_watch_only")
        else:
            warnings.append("signal_state_not_production_ready")
        return StrategyExecutionGate(
            decision="watch_only",
            production_allowed=False,
            priority_board_allowed=False,
            production_score_allowed=False,
            reasons=_dedupe([*reasons, f"signal_state:{signal_state}"]),
            warning_tags=_dedupe(warnings),
        )

    if not payload.participates_in_priority_board:
        return StrategyExecutionGate(
            decision="research_only",
            production_allowed=False,
            priority_board_allowed=False,
            production_score_allowed=False,
            reasons=_dedupe([*reasons, "non_production_strategy"]),
            warning_tags=["non_production_strategy"],
        )

    return StrategyExecutionGate(
        decision="allow_production",
        production_allowed=True,
        priority_board_allowed=True,
        production_score_allowed=True,
        reasons=_dedupe(reasons),
        warning_tags=[],
    )


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        item = str(value or "").strip()
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result
