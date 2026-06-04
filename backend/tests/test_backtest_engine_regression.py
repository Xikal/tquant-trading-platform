from __future__ import annotations

from app.services.execution_model import build_backtest_execution_model_preview
from test_backtest_v2_engine_contract import _ProviderStub, _config, engine_module
from test_decision_context_portfolio_executor import _trade


def test_backtest_engine_regression_keeps_canonical_engine_outputs() -> None:
    result = getattr(engine_module, "BacktestEngine")(_ProviderStub()).run(_config())

    assert result.orders
    assert result.trades
    assert result.metrics["trade_count"] >= 1
    assert result.metrics["execution_assumptions"]["execution_model"] == _config().execution_model


def test_execution_model_preview_does_not_replace_backtest_fact_source() -> None:
    preview = build_backtest_execution_model_preview(
        [
            _trade("2026-05-20", 2.0, symbol="000001", production_score=80),
            _trade("2026-05-21", -1.0, symbol="000002", production_score=72),
        ]
    )

    assert preview["replacement_enabled"] is False
    assert preview["final_fact_source"] == "portfolio_backtest_metrics"
