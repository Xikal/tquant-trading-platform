from __future__ import annotations

from scripts.low_buy_market_backtest_reporting import portfolio_backtest_metrics

from app.core.config import get_settings
from app.services.execution_model import build_backtest_execution_model_preview
from test_decision_context_portfolio_executor import _trade


def test_execution_model_shared_rules_flag_defaults_off() -> None:
    get_settings.cache_clear()

    assert get_settings().execution_model_shared_rules_enabled is False


def test_backtest_execution_model_preview_matches_portfolio_metrics_golden() -> None:
    outcomes = [
        _trade("2026-05-20", 2.0, symbol="000001", production_score=80),
        _trade("2026-05-21", -1.0, symbol="000002", production_score=72),
        _trade("2026-05-22", 3.0, symbol="000003", production_score=88),
    ]

    preview = build_backtest_execution_model_preview(outcomes)
    canonical5 = portfolio_backtest_metrics(outcomes, max_positions=5)
    canonical10 = portfolio_backtest_metrics(outcomes, max_positions=10)

    assert preview["mode"] == "parallel_preview"
    assert preview["replacement_enabled"] is False
    assert preview["final_fact_source"] == "portfolio_backtest_metrics"
    assert preview["max_5"]["portfolio_return_pct"] == canonical5["portfolio_return_pct"]
    assert preview["max_10"]["portfolio_return_pct"] == canonical10["portfolio_return_pct"]
    assert all(preview["parity"]["max_5"].values())
    assert all(preview["parity"]["max_10"].values())
    assert preview["event_counts"] == {"exit": 3, "fill": 3, "order": 3, "position": 3, "signal": 3}
