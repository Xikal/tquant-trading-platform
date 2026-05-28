from __future__ import annotations

from backend.tests.main_force_model_test_helpers import main_force_candidate, washout_history
from app.services.low_buy.main_force_model_enrichment import enrich_candidate_with_main_force_model


def test_enrichment_adds_readonly_advice_without_mutating_candidate() -> None:
    candidate = main_force_candidate()

    enriched = enrich_candidate_with_main_force_model(
        None,
        candidate=candidate,
        history_rows=washout_history(),
        market_state="repair",
        sector_strength=0.72,
        market_strength=0.65,
        record_shadow=False,
    )

    assert candidate.main_force_advice == {}
    assert enriched.score == candidate.score
    assert enriched.entry_zone_low == candidate.entry_zone_low
    assert enriched.stop_loss == candidate.stop_loss
    assert enriched.main_force_advice["production_effect"] == "readonly_shadow"
    assert enriched.main_force_advice["action"] in {"buy_probe", "buy_confirmed", "wait_confirm", "observe"}
    assert enriched.main_force_advice["feature_snapshot"]["max_source_date"] <= "2026-04-24"


def test_enrichment_fallback_is_observable_when_history_is_insufficient() -> None:
    enriched = enrich_candidate_with_main_force_model(
        None,
        candidate=main_force_candidate(data_quality="ok"),
        history_rows=washout_history(days=5),
        market_state="repair",
        sector_strength=0.7,
        market_strength=0.6,
        record_shadow=False,
    )

    advice = enriched.main_force_advice
    assert advice["action"] == "blocked"
    assert advice["fallback_reason"] in {"data_quality", None} or advice["risk_flags"]
    assert advice["risk_flags"]


def test_enrichment_blocks_risk_candidate_but_keeps_original_signal() -> None:
    candidate = main_force_candidate(risk_tier="block", buy_signal_state="buy_now")

    enriched = enrich_candidate_with_main_force_model(
        None,
        candidate=candidate,
        history_rows=washout_history(),
        market_state="repair",
        sector_strength=0.7,
        market_strength=0.6,
        record_shadow=False,
    )

    assert enriched.buy_signal_state == "buy_now"
    assert enriched.main_force_advice["action"] == "blocked"
    assert any("硬风险" in item for item in enriched.main_force_advice["risk_flags"])
