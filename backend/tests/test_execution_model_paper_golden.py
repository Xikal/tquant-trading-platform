from __future__ import annotations

from scripts.low_buy_market_backtest_reporting import portfolio_backtest_metrics

from app.services.execution_model import build_paper_execution_model_preview
from test_decision_context_portfolio_executor import _trade


def test_paper_execution_model_preview_matches_existing_portfolio_preview() -> None:
    outcomes = [
        _trade("2026-05-20", 1.5, symbol="000001", exit_trade_date="2026-05-22"),
        _trade("2026-05-20", -0.5, symbol="000002", exit_trade_date="2026-05-22"),
        _trade("2026-05-21", 2.0, symbol="000003", exit_trade_date="2026-05-23"),
    ]

    preview = build_paper_execution_model_preview(outcomes)
    canonical5 = portfolio_backtest_metrics(outcomes, max_positions=5)

    assert preview["source"] == "paper"
    assert preview["replacement_enabled"] is False
    assert preview["max_5"]["trade_count"] == canonical5["trade_count"]
    assert all(preview["parity"]["max_5"].values())
    assert preview["position_summary"]["position_count"] == 3
    assert preview["exit_reason_counts"] == {"测试退出": 3}
