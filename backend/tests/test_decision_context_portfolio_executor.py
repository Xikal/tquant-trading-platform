from __future__ import annotations

from scripts.low_buy_market_backtest_reporting import TradeOutcome, backtest_performance_metrics, portfolio_backtest_metrics

from app.services.decision_context.portfolio_executor import (
    run_portfolio_execution,
    run_portfolio_execution_preview,
)


def test_portfolio_executor_reuses_max_positions_and_duplicate_symbol_rules() -> None:
    outcomes = [
        _trade("2026-05-20", 1, symbol="000001", exit_trade_date="2026-05-22"),
        _trade("2026-05-20", 1, symbol="000002", exit_trade_date="2026-05-22"),
        _trade("2026-05-20", 1, symbol="000003", exit_trade_date="2026-05-22"),
        _trade("2026-05-20", 1, symbol="000004", exit_trade_date="2026-05-22"),
        _trade("2026-05-20", 1, symbol="000005", exit_trade_date="2026-05-22"),
        _trade("2026-05-20", 1, symbol="000006", exit_trade_date="2026-05-22"),
        _trade("2026-05-21", 1, symbol="000001", exit_trade_date="2026-05-23"),
    ]

    result = run_portfolio_execution(outcomes, max_positions=5, max_daily_per_strategy=None, max_per_sector=None)

    assert result["max_positions"] == 5
    assert result["trade_count"] == 5
    assert result["skipped_by_max_positions"] == 1
    assert result["skipped_by_duplicate_symbol"] == 1
    assert result["skip_reason_counts"]["max_positions"] == 1
    assert result["skip_reason_counts"]["duplicate_symbol_open"] == 1


def test_portfolio_executor_matches_24m_report_portfolio_backtests() -> None:
    outcomes = [
        _trade("2026-05-20", 2.0, symbol="000001", production_score=80),
        _trade("2026-05-21", -1.0, symbol="000002", production_score=72),
        _trade("2026-05-22", 3.0, symbol="000003", production_score=88),
    ]

    report_metrics = backtest_performance_metrics(outcomes)["portfolio_backtests"]
    preview = run_portfolio_execution_preview(outcomes)

    assert preview["max_5"]["portfolio_return_pct"] == report_metrics["max_5"]["portfolio_return_pct"]
    assert preview["max_10"]["portfolio_return_pct"] == report_metrics["max_10"]["portfolio_return_pct"]
    assert preview["max_5"]["skip_reason_counts"] == portfolio_backtest_metrics(outcomes, max_positions=5)["skip_reason_counts"]


def _trade(
    signal_date: str,
    net_return_pct: float,
    *,
    symbol: str,
    exit_trade_date: str | None = None,
    strategy_key: str = "first_board",
    sector_name: str = "测试板块",
    production_score: float | None = None,
) -> TradeOutcome:
    return TradeOutcome(
        symbol=symbol,
        name="测试",
        signal_date=signal_date,
        strategy_key=strategy_key,
        buy_signal_state="buy_now",
        entry_price=10.0,
        execution_status="filled",
        net_return_pct=net_return_pct,
        execution_exit_reason="测试退出",
        return_1d=net_return_pct,
        return_2d=net_return_pct,
        return_3d=net_return_pct,
        return_4d=net_return_pct,
        return_5d=net_return_pct,
        max_gain_5d=max(net_return_pct, 0.0),
        max_drawdown_5d=min(net_return_pct, 0.0),
        entry_trade_date=signal_date,
        exit_trade_date=exit_trade_date or signal_date,
        sector_name=sector_name,
        market_state="repair",
        production_score=production_score,
    )
