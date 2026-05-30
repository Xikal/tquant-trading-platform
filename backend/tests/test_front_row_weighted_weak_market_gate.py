from __future__ import annotations

from app.services.low_buy.weak_market_candidate_gate import evaluate_weak_market_candidate


def _row(**overrides):
    row = {
        "market_state": "low_volume_wait",
        "buy_signal_state": "soft_buy_now",
        "front_row_tier": "leader_hot",
        "production_score": 90,
    }
    row.update(overrides)
    return row


def test_weak_buy_now_demoted_under_preferred_policy() -> None:
    result = evaluate_weak_market_candidate(_row(buy_signal_state="buy_now"), policy_name="weak_soft_score86_cap20")

    assert not result.allowed_for_paper
    assert result.reason == "weak_market_buy_now_demoted"


def test_weak_soft_buy_score_below_threshold_demoted() -> None:
    result = evaluate_weak_market_candidate(_row(production_score=85), policy_name="weak_soft_score86_cap20")

    assert not result.allowed_for_paper
    assert result.reason == "weak_market_score_below_policy"


def test_weak_soft_buy_above_threshold_allowed() -> None:
    result = evaluate_weak_market_candidate(_row(production_score=90), policy_name="weak_soft_score86_cap20")

    assert result.allowed_for_paper
    assert not result.demoted_to_watch


def test_retreat_market_always_blocked() -> None:
    result = evaluate_weak_market_candidate(_row(market_state="panic"), policy_name="weak_soft_score86_cap20")

    assert not result.allowed_for_paper
    assert result.reason == "retreat_market_no_new_position"


def test_near_entry_never_allowed() -> None:
    result = evaluate_weak_market_candidate(_row(buy_signal_state="near_entry"), policy_name="weak_soft_score86_cap20")

    assert not result.allowed_for_paper
    assert result.reason == "near_entry_watch_only"
