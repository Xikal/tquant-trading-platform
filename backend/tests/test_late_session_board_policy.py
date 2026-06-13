from __future__ import annotations

from app.services.low_buy.late_session_policy import (
    FORMAL_LATE_SESSION_STRATEGIES,
    LATE_SESSION_LOW_SAMPLE_CAPPED_STRATEGIES,
    classify_late_session_strategy,
    late_session_score_cap,
    late_session_strategy_allowed_for_formal,
)


def test_formal_late_session_strategy_whitelist_is_narrow() -> None:
    assert FORMAL_LATE_SESSION_STRATEGIES == {
        "first_board",
        "volume_shrink",
        "late_session_strong_support",
    }
    assert late_session_strategy_allowed_for_formal("first_board") is True
    assert late_session_strategy_allowed_for_formal("volume_shrink") is True
    assert late_session_strategy_allowed_for_formal("late_session_strong_support") is True
    assert late_session_strategy_allowed_for_formal("classic_retrace") is False
    assert late_session_strategy_allowed_for_formal("deep_pullback") is False


def test_low_sample_strategy_is_capped_not_promoted() -> None:
    assert LATE_SESSION_LOW_SAMPLE_CAPPED_STRATEGIES == {"late_session_strong_support"}
    assert classify_late_session_strategy("late_session_strong_support") == "auxiliary_capped"
    assert classify_late_session_strategy("first_board") == "core"
    assert classify_late_session_strategy("classic_retrace") == "research_only"
    assert late_session_score_cap("late_session_strong_support", 95) == 72.0
    assert late_session_score_cap("first_board", 95) == 95.0
