from __future__ import annotations

from app.services.decision_context.hard_risk_filter import (
    HardRiskInput,
    evaluate_hard_risk_gate,
    hard_risk_gate_from_snapshot,
)


def test_hard_risk_blocks_st_stock() -> None:
    result = evaluate_hard_risk_gate(
        HardRiskInput(symbol="000001", name="*ST测试", is_st=True, status="active", data_quality="ok")
    )

    assert result.decision == "block"
    assert "ST" in " ".join(result.reasons)


def test_hard_risk_blocks_invalid_ohlc() -> None:
    result = evaluate_hard_risk_gate(
        HardRiskInput(
            symbol="000002",
            name="测试股份",
            is_st=False,
            status="active",
            data_quality="invalid_ohlc",
            open_price=0,
            high_price=10,
            low_price=9,
            close_price=9.5,
        )
    )

    assert result.decision == "block"
    assert result.evidence["data_quality"] == "invalid_ohlc"


def test_hard_risk_filter_flag_disabled_allows_existing_path(monkeypatch) -> None:
    monkeypatch.setenv("DECISION_CONTEXT_ENABLED", "false")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        result = hard_risk_gate_from_snapshot(
            {"hard_risk_gate": {"decision": "block", "score": 0, "reasons": ["ST"]}}
        )
    finally:
        get_settings.cache_clear()

    assert result.decision == "allow"
    assert result.evidence["feature_flag_disabled"] is True


def test_hard_risk_reduces_when_limit_metadata_missing() -> None:
    result = evaluate_hard_risk_gate(
        HardRiskInput(
            symbol="600000",
            name="浦发银行",
            is_st=False,
            status="active",
            data_quality="ok",
            current_price=10.0,
            up_limit=None,
            down_limit=None,
            source="auto",
        )
    )

    assert result.decision == "reduce"
    assert any("涨跌停" in reason for reason in result.reasons)
