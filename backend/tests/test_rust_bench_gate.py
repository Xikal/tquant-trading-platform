from __future__ import annotations

from pathlib import Path

from scripts.check_rust_bench_baseline import parse_results


def test_rust_bench_baseline_covers_finance_hot_path_metrics() -> None:
    baseline = Path(__file__).resolve().parents[2] / "docs" / "reports" / "rust-bench-baseline.json"
    text = baseline.read_text(encoding="utf-8")
    for name in (
        "finance/max_drawdown/20000",
        "finance/rolling_mean_20/20000",
        "finance/atr_wilder_14/20000",
        "finance/rsi_wilder_14/20000",
        "finance/vwap/20000",
        "finance/rank_ic/20000",
    ):
        assert name in text


def test_rust_bench_output_parser_accepts_bencher_format() -> None:
    text = """
test finance/max_drawdown/20000 ... bench:       10444 ns/iter (+/- 775)
test finance/atr_wilder_14/20000 ... bench:      103154 ns/iter (+/- 7239)
"""
    assert parse_results(text) == {
        "finance/max_drawdown/20000": 10444,
        "finance/atr_wilder_14/20000": 103154,
    }
