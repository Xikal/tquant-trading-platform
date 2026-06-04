from __future__ import annotations

import hashlib
import json

from app.core.config import get_settings
from app.services.low_buy.production_scoring import score_low_buy_candidate_for_production
from app.services.strategy_engine.low_buy_adapter import low_buy_strategy_engine_output
from test_low_buy_production_scoring import _front_row_candidate


def test_strategy_engine_adapter_feature_flag_defaults_off() -> None:
    get_settings.cache_clear()

    assert get_settings().strategy_engine_adapter_enabled is False


def test_low_buy_adapter_matches_existing_production_scoring_golden() -> None:
    candidate = _front_row_candidate("first_board")
    existing = score_low_buy_candidate_for_production(candidate)
    output = low_buy_strategy_engine_output(candidate)

    assert output.production_score == existing.production_score
    assert output.watch_score == existing.watch_score
    assert output.score_components == existing.score_components
    assert output.metadata["production_decision"] == existing.decision
    assert output.metadata["front_row_tier"] == existing.front_row_tier
    assert output.metadata["score_cap"] == existing.score_cap
    assert output.decision == "production_candidate"
    assert _golden_hash(output.as_payload()) == "b0bd63801097"


def test_low_buy_adapter_research_strategy_has_no_production_score() -> None:
    candidate = _front_row_candidate("n_pattern_long_wash")
    existing = score_low_buy_candidate_for_production(candidate)
    output = low_buy_strategy_engine_output(candidate)

    assert existing.production_score is None
    assert output.production_score is None
    assert output.watch_score == existing.watch_score
    assert output.decision == "research_only"
    assert "non_production_strategy" in output.exclusion_reasons


def test_low_buy_adapter_near_entry_stays_watch_only() -> None:
    candidate = _front_row_candidate("first_board").model_copy(update={"buy_signal_state": "near_entry"})
    existing = score_low_buy_candidate_for_production(candidate)
    output = low_buy_strategy_engine_output(candidate)

    assert existing.production_score is None
    assert output.production_score is None
    assert output.watch_score == existing.watch_score
    assert output.decision == "watch_only"
    assert "near_entry_watch_only" in output.warning_tags


def _golden_hash(payload: dict) -> str:
    stable = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()[:12]
