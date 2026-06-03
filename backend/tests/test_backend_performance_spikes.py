from __future__ import annotations

from backend.scripts.backtest_24m_precompute_spike import SpikeDataset, run_backtest_24m_precompute_spike
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
    result = run_backtest_24m_precompute_spike(count=160, prefer_real_data=False)

    assert result["max5_equal"] is True
    assert result["max10_equal"] is True
    assert result["parity"]["all_equal"] is True
    assert result["parity"]["max5"]["profit_factor"] is True
    assert result["parity"]["max5"]["avg_trade_return_pct"] is True
    assert result["parity"]["max5"]["portfolio_return_pct"] is True
    assert result["parity"]["max5"]["max_drawdown_pct"] is True
    assert result["parity"]["max5"]["trade_count"] is True
    assert result["parity"]["max10"]["profit_factor"] is True
    assert result["parity"]["max10"]["avg_trade_return_pct"] is True
    assert result["parity"]["max10"]["portfolio_return_pct"] is True
    assert result["parity"]["max10"]["max_drawdown_pct"] is True
    assert result["parity"]["max10"]["trade_count"] is True
    assert result["baseline"]["max5"] == result["precompute"]["max5"]
    assert result["baseline"]["max10"] == result["precompute"]["max10"]
    assert result["final_executor"] == "portfolio_backtest_metrics"
    assert result["productionized"] is False


def test_backtest_24m_precompute_spike_marks_real_data_blocked(monkeypatch) -> None:
    def fake_loader(count: int) -> SpikeDataset:
        return SpikeDataset(
            inputs=[],
            source="real_daily_bars",
            status="blocked",
            reason="database_unavailable:test",
            coverage={},
        )

    monkeypatch.setattr("backend.scripts.backtest_24m_precompute_spike.load_real_daily_bar_inputs", fake_loader)

    result = run_backtest_24m_precompute_spike(count=24)

    assert result["real_data"]["status"] == "blocked"
    assert result["real_data"]["reason"] == "database_unavailable:test"
    assert result["data_status"] == "fixture_fallback"
    assert result["input_source"] == "fixture"
    assert result["parity"]["all_equal"] is True
