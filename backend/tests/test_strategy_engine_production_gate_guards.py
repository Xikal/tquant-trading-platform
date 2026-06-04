from __future__ import annotations

from app.models.schemas import LowBuyHardRiskOut
from app.services.strategy_engine.gates import StrategyGateInput, evaluate_strategy_gate
from app.services.strategy_engine.low_buy_adapter import low_buy_strategy_engine_output, low_buy_strategy_gate_input
from app.services.low_buy.strategy_lanes import FRONT_ROW_ONLY_VARIANT
from test_low_buy_production_scoring import _front_row_candidate


def test_research_only_gate_blocks_priority_and_production_score() -> None:
    gate = evaluate_strategy_gate(
        StrategyGateInput(
            strategy_key="n_pattern_short_wash",
            signal_state="soft_buy_now",
            participates_in_priority_board=False,
            research_only=True,
        )
    )

    assert gate.production_allowed is False
    assert gate.priority_board_allowed is False
    assert gate.production_score_allowed is False
    assert gate.decision == "research_only"


def test_front_row_only_variant_is_watch_only_not_production_filter_rewrite() -> None:
    candidate = _front_row_candidate("first_board")
    gate_input = low_buy_strategy_gate_input(candidate, strategy_variant=FRONT_ROW_ONLY_VARIANT)
    output = low_buy_strategy_engine_output(candidate, strategy_variant=FRONT_ROW_ONLY_VARIANT)

    assert gate_input.front_row_only is True
    assert output.production_score is None
    assert output.watch_score is not None
    assert output.decision == "watch_only"
    assert "front_row_only_watch" in output.exclusion_reasons


def test_shadow_paper_candidate_cannot_enter_production_ranking() -> None:
    candidate = _front_row_candidate("first_board").model_copy(update={"paper_enabled": True})
    output = low_buy_strategy_engine_output(candidate)

    assert output.production_score is None
    assert output.decision == "shadow_paper_only"
    assert "shadow_paper_only" in output.exclusion_reasons


def test_hard_risk_blocked_candidate_has_no_production_score() -> None:
    candidate = _front_row_candidate("first_board").model_copy(
        update={
            "hard_risk": LowBuyHardRiskOut(
                level="block",
                score_penalty=99.0,
                execution_blocked=True,
                reasons=["流动性不足"],
                tags=["硬风控:流动性"],
            )
        }
    )

    output = low_buy_strategy_engine_output(candidate)

    assert output.production_score is None
    assert output.decision == "blocked"
    assert "hard_risk_execution_blocked" in output.exclusion_reasons
    assert "strategy_blocked" in output.warning_tags
