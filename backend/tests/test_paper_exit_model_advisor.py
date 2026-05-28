from __future__ import annotations

import json
from dataclasses import replace

import pytest

from app.core.config import get_settings
from app.services.paper.exit_model_advisor import ExitModelAdvisor
from app.services.paper.exit_model_schema import ExitModelFeatureSnapshot


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _features(**overrides) -> ExitModelFeatureSnapshot:
    base = ExitModelFeatureSnapshot(
        symbol="600000",
        name="浦发银行",
        strategy_key="first_board",
        as_of="2026-05-28T10:30:00",
        current_price=10.8,
        cost_basis=10.0,
        pnl_pct=8.0,
        max_profit_pct=10.0,
        pullback_from_high_pct=2.0,
        hold_days=3,
        quantity=1000,
        available_quantity=1000,
        rule_action="hold",
        data_quality="fresh",
        feature_values={
            "pnl_pct": 8.0,
            "max_profit_pct": 10.0,
            "pullback_from_high_pct": 2.0,
            "hold_days": 3.0,
            "available_ratio": 1.0,
            "position_pct": 10.0,
            "vwap_deviation_pct": 1.0,
            "rsi": 64.0,
            "atr_pct": 1.2,
            "high_pullback_ratio": 0.3,
            "volume_release_ratio": 1.1,
            "market_strength": 0.5,
            "sector_strength": 0.6,
            "rule_sell_ratio": 0.0,
        },
    )
    return replace(base, **overrides)


def test_exit_model_advisor_falls_back_when_model_unavailable(monkeypatch) -> None:
    monkeypatch.setenv("PAPER_EXIT_MODEL_ARTIFACT_PATH", "")
    get_settings.cache_clear()

    suggestion = ExitModelAdvisor().suggest(_features())

    assert suggestion.shadow_only is True
    assert suggestion.action == "hold"
    assert suggestion.effective_action == "hold"
    assert suggestion.fallback_reason == "model_unavailable"


def test_exit_model_advisor_blocks_stale_data_before_prediction(tmp_path, monkeypatch) -> None:
    artifact = tmp_path / "model.json"
    artifact.write_text(json.dumps({"weights": {"pnl_pct": 1.0}, "confidence": 0.99, "action": "sell_all"}), encoding="utf-8")
    monkeypatch.setenv("PAPER_EXIT_MODEL_ARTIFACT_PATH", str(artifact))
    get_settings.cache_clear()

    suggestion = ExitModelAdvisor().suggest(_features(data_quality="partial"))

    assert suggestion.action == "hold"
    assert suggestion.fallback_reason == "data_quality_partial"
    assert suggestion.effective_action == "hold"


def test_exit_model_advisor_never_overrides_hard_stop(tmp_path, monkeypatch) -> None:
    artifact = tmp_path / "model.json"
    artifact.write_text(json.dumps({"weights": {"pnl_pct": -1.0}, "confidence": 0.99, "action": "hold"}), encoding="utf-8")
    monkeypatch.setenv("PAPER_EXIT_MODEL_ARTIFACT_PATH", str(artifact))
    get_settings.cache_clear()

    suggestion = ExitModelAdvisor().suggest(_features(rule_action="hard_stop", rule_sell_ratio=1.0))

    assert suggestion.shadow_only is True
    assert suggestion.action == "sell_all"
    assert suggestion.effective_action == "hard_stop"
    assert suggestion.fallback_reason == "hard_stop_rule_priority"
    assert suggestion.safety_blocked is True


def test_exit_model_advisor_enforces_rule_floor(tmp_path, monkeypatch) -> None:
    artifact = tmp_path / "model.json"
    artifact.write_text(
        json.dumps({
            "weights": {"pnl_pct": 0.0},
            "intercept": 0.1,
            "confidence": 0.9,
            "action": "hold",
        }),
        encoding="utf-8",
    )
    monkeypatch.setenv("PAPER_EXIT_MODEL_ARTIFACT_PATH", str(artifact))
    get_settings.cache_clear()

    suggestion = ExitModelAdvisor().suggest(_features(rule_action="sell_50", rule_sell_ratio=0.5))

    assert suggestion.action == "sell_50"
    assert suggestion.effective_action == "sell_50"
    assert suggestion.fallback_reason == "rule_action_floor"
    assert suggestion.safety_blocked is True
