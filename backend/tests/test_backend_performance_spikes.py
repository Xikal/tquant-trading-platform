from __future__ import annotations

from backend.scripts.backtest_24m_precompute_spike import run_backtest_24m_precompute_spike
from backend.scripts.parallel_scan_spike import fixture_symbols, run_parallel_scan_spike


def test_parallel_scan_spike_keeps_golden_ordering_and_payload() -> None:
    result = run_parallel_scan_spike(
        symbols=fixture_symbols(120),
        trade_date="2026-06-03",
        strategy_key="first_board",
        max_workers=6,
        simulate_io_seconds=0.0,
    )

    assert result["symbol_count"] == 120
    assert result["golden_equal"] is True
    assert result["ordering_equal"] is True
    assert result["serial"]["candidate_count"] == result["parallel"]["candidate_count"]
    assert result["db_query_delta"] == 0
    assert result["productionized"] is False


def test_backtest_24m_precompute_spike_preserves_portfolio_metrics() -> None:
    result = run_backtest_24m_precompute_spike(count=160)

    assert result["max5_equal"] is True
    assert result["max10_equal"] is True
    assert result["baseline"]["max5"] == result["precompute"]["max5"]
    assert result["final_executor"] == "portfolio_backtest_metrics"
    assert result["productionized"] is False

