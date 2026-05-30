from __future__ import annotations

from app.services.decision_context.market_gate import (
    MARKET_GATE_MULTIPLIER,
    MarketGateInput,
    evaluate_market_gate,
    market_gate_from_context,
)


def test_market_gate_allows_strong_repair_state() -> None:
    result = evaluate_market_gate(
        MarketGateInput(
            market_state="repair",
            market_state_strength=0.78,
            limit_up_count=88,
            limit_down_count=2,
            turnover_amount=1_200_000_000_000,
            index_trend="up",
            hot_sector_count=6,
        )
    )

    assert result.decision == "allow"
    assert result.score >= 75


def test_market_gate_blocks_retreat_state_for_new_buy() -> None:
    result = evaluate_market_gate(
        MarketGateInput(
            market_state="high_flyer_retreat",
            market_state_strength=0.18,
            limit_up_count=21,
            limit_down_count=62,
            turnover_amount=720_000_000_000,
            index_trend="down",
            hot_sector_count=1,
        )
    )

    assert result.decision == "block"
    assert "退潮" in " ".join(result.reasons)


def test_market_level_missing_data_reduces_instead_of_global_block() -> None:
    result = evaluate_market_gate(
        MarketGateInput(
            market_state="",
            market_state_strength=None,
            limit_up_count=None,
            limit_down_count=None,
            turnover_amount=None,
            index_trend="",
            hot_sector_count=None,
            previous_market_state="repair",
        )
    )

    assert result.decision == "reduce"
    assert result.evidence["data_quality"] == "degraded"
    assert result.evidence["effective_market_state"] == "repair"
    assert MARKET_GATE_MULTIPLIER[result.decision] > 0


def test_market_gate_flag_disabled_allows_existing_priority_path(monkeypatch) -> None:
    class Context:
        market_state = "high_flyer_retreat"
        market_state_strength = 0.1
        limit_up_count = 5
        limit_down_count = 80
        stock_median_change = -3.0
        hot_industries = []
        previous_market_state = "repair"
        breadth_ready = True
        emotion_ready = True

    monkeypatch.setenv("MARKET_GATE_PRODUCTION_ENABLED", "false")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        result = market_gate_from_context(Context())
    finally:
        get_settings.cache_clear()

    assert result.decision == "allow"
    assert result.evidence["feature_flag_disabled"] is True
