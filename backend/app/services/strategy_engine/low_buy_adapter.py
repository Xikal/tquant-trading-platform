from __future__ import annotations

from typing import Any

from app.services.low_buy.production_scoring import score_low_buy_candidate_for_production
from app.services.low_buy.strategy_lanes import FRONT_ROW_ONLY_VARIANT
from app.services.low_buy.strategy_policy import participates_in_priority_board
from app.services.strategy_engine.gates import StrategyGateInput, evaluate_strategy_gate
from app.services.strategy_engine.outputs import StrategyEngineOutput


ENGINE_ADAPTER_VERSION = "low-buy-adapter-v1"


def low_buy_strategy_gate_input(candidate: Any, *, strategy_variant: str = "baseline") -> StrategyGateInput:
    strategy_key = _text(candidate, "strategy_key")
    return StrategyGateInput(
        strategy_key=strategy_key,
        signal_state=_text(candidate, "buy_signal_state", "watch"),
        participates_in_priority_board=participates_in_priority_board(strategy_key),
        research_only=bool(getattr(candidate, "research_only", False)),
        watch_only=bool(getattr(candidate, "watch_only", False)),
        shadow_paper=bool(getattr(candidate, "paper_enabled", False)),
        front_row_only=str(strategy_variant or "") == FRONT_ROW_ONLY_VARIANT,
        blocked=_risk_blocked(candidate),
        reasons=_input_reasons(candidate),
    )


def low_buy_strategy_engine_output(
    candidate: Any,
    *,
    market_context: Any | None = None,
    strategy_variant: str = "baseline",
) -> StrategyEngineOutput:
    """Map existing low-buy scoring into the strategy-engine envelope.

    This is a parity adapter only. It deliberately reuses the existing
    low-buy production scoring function and does not change ranking.
    """

    scoring = score_low_buy_candidate_for_production(candidate, market_context=market_context, mode="shadow")
    gate_input = low_buy_strategy_gate_input(candidate, strategy_variant=strategy_variant)
    gate = evaluate_strategy_gate(gate_input)
    return StrategyEngineOutput(
        strategy_key=gate_input.strategy_key,
        symbol=_text(candidate, "symbol"),
        signal_state=gate_input.signal_state,
        production_score=scoring.production_score if gate.production_score_allowed else None,
        watch_score=scoring.watch_score,
        score_components=dict(scoring.score_components),
        exclusion_reasons=_dedupe([*scoring.exclusion_reasons, *gate.reasons]),
        warning_tags=_dedupe([*scoring.warning_tags, *gate.warning_tags]),
        decision=_output_decision(scoring.decision, gate),
        source="low_buy_adapter",
        metadata={
            "adapter_version": ENGINE_ADAPTER_VERSION,
            "production_decision": scoring.decision,
            "front_row_tier": scoring.front_row_tier,
            "score_cap": scoring.score_cap,
            "production_scoring_config_version": scoring.config_version,
            "gate": gate.as_payload(),
        },
    )


def _text(candidate: Any, field: str, default: str = "") -> str:
    return str(getattr(candidate, field, default) or default).strip()


def _risk_blocked(candidate: Any) -> bool:
    hard_risk = getattr(candidate, "hard_risk", None)
    if hard_risk is None:
        return False
    return bool(getattr(hard_risk, "execution_blocked", False) or getattr(hard_risk, "level", "") == "block")


def _input_reasons(candidate: Any) -> list[str]:
    reasons: list[str] = []
    for field in ("exclusion_reasons", "warning_tags"):
        values = getattr(candidate, field, None) or []
        if isinstance(values, (list, tuple, set)):
            reasons.extend(str(item) for item in values if str(item or "").strip())
    return reasons


def _output_decision(scoring_decision: str, gate) -> str:  # noqa: ANN001
    if gate.decision == "blocked" or scoring_decision == "excluded":
        return "blocked"
    if gate.decision == "research_only":
        return "research_only"
    if gate.decision == "watch_only":
        if "shadow_paper_only" in gate.reasons:
            return "shadow_paper_only"
        return "watch_only"
    return "production_candidate"


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        item = str(value or "").strip()
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result
