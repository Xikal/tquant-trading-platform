from __future__ import annotations

from dataclasses import dataclass

from app.services.low_buy.strategy_lanes import FRONT_ROW_ONLY_VARIANT
from app.services.strategy_engine import (
    StrategyEngineOutput,
    StrategyGateInput,
    evaluate_strategy_gate,
    low_buy_strategy_gate_input,
)


@dataclass(frozen=True)
class _Candidate:
    strategy_key: str = "first_board"
    buy_signal_state: str = "soft_buy_now"
    research_only: bool = False
    watch_only: bool = False
    paper_enabled: bool = False
    hard_risk: object | None = None
    exclusion_reasons: list[str] | None = None
    warning_tags: list[str] | None = None


@dataclass(frozen=True)
class _HardRisk:
    level: str = "block"
    execution_blocked: bool = True


def test_strategy_engine_output_has_canonical_payload_fields() -> None:
    output = StrategyEngineOutput(
        strategy_key="first_board",
        symbol="600000",
        signal_state="soft_buy_now",
        production_score=88.0,
        watch_score=72.0,
        score_components={"base": 60.0},
        warning_tags=["front_row_weighted_shadow"],
    )

    payload = output.as_payload()

    assert payload["production_score"] == 88.0
    assert payload["watch_score"] == 72.0
    assert payload["score_components"] == {"base": 60.0}
    assert payload["exclusion_reasons"] == []
    assert payload["warning_tags"] == ["front_row_weighted_shadow"]


def test_research_only_and_non_production_strategy_never_allow_production() -> None:
    research_flag = evaluate_strategy_gate(
        StrategyGateInput(
            strategy_key="first_board",
            signal_state="soft_buy_now",
            participates_in_priority_board=True,
            research_only=True,
        )
    )
    research_strategy = evaluate_strategy_gate(
        StrategyGateInput(
            strategy_key="n_pattern_short_wash",
            signal_state="soft_buy_now",
            participates_in_priority_board=False,
        )
    )

    assert research_flag.production_score_allowed is False
    assert research_flag.decision == "research_only"
    assert research_strategy.production_score_allowed is False
    assert research_strategy.decision == "research_only"
    assert "non_production_strategy" in research_strategy.reasons


def test_near_entry_watch_and_shadow_paper_never_allow_production_score() -> None:
    near_entry = evaluate_strategy_gate(
        StrategyGateInput(
            strategy_key="first_board",
            signal_state="near_entry",
            participates_in_priority_board=True,
        )
    )
    shadow = evaluate_strategy_gate(
        StrategyGateInput(
            strategy_key="first_board",
            signal_state="soft_buy_now",
            participates_in_priority_board=True,
            shadow_paper=True,
        )
    )

    assert near_entry.decision == "watch_only"
    assert near_entry.production_score_allowed is False
    assert "near_entry_watch_only" in near_entry.warning_tags
    assert shadow.decision == "watch_only"
    assert shadow.production_score_allowed is False
    assert "shadow_paper_only" in shadow.reasons


def test_low_buy_adapter_preserves_strategy_policy_and_front_row_only_gate() -> None:
    baseline = evaluate_strategy_gate(low_buy_strategy_gate_input(_Candidate()))
    research = evaluate_strategy_gate(low_buy_strategy_gate_input(_Candidate(strategy_key="n_pattern_long_wash")))
    front_row_only = evaluate_strategy_gate(
        low_buy_strategy_gate_input(_Candidate(), strategy_variant=FRONT_ROW_ONLY_VARIANT)
    )

    assert baseline.production_score_allowed is True
    assert baseline.priority_board_allowed is True
    assert research.production_score_allowed is False
    assert research.priority_board_allowed is False
    assert front_row_only.production_score_allowed is False
    assert front_row_only.priority_board_allowed is False
    assert "front_row_only_watch" in front_row_only.reasons


def test_hard_risk_blocks_before_production_gate() -> None:
    gate = evaluate_strategy_gate(low_buy_strategy_gate_input(_Candidate(hard_risk=_HardRisk())))

    assert gate.decision == "blocked"
    assert gate.production_score_allowed is False
    assert gate.priority_board_allowed is False
    assert "blocked" in gate.reasons
