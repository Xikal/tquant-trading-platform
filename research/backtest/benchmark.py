from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from research.backtest.strategy_validation import (
    STANDARD_REPORT_FIELDS,
    _information_coefficient,
    _max_drawdown,
    _numeric_series,
    _sharpe,
)
from research.data_sync.tquant_to_qlib import qlib_status, read_offline_table


def benchmark_summary(path: str | Path) -> dict:
    report = build_benchmark_report(path)
    return {
        "rows": report["sample_count"],
        "avg_return_3d": report["avg_return_3d"],
        "win_rate_3d": report["win_rate"],
        **report,
    }


def build_benchmark_report(path: str | Path) -> dict[str, object]:
    """Build a standard benchmark report without requiring qlib or online data."""

    source = Path(path)
    frame = read_offline_table(source)
    returns = _numeric_series(frame, "return_3d") if not frame.empty else pd.Series(dtype=float)
    if returns.empty:
        returns = _numeric_series(frame, "return")
    if returns.empty:
        return _empty_benchmark(source)
    win_rate = round(float((returns > 0).mean() * 100), 2)
    return {
        "status": "ok",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_path": str(source),
        "qlib": qlib_status(),
        "sample_count": int(len(returns)),
        "win_rate": win_rate,
        "avg_return_3d": round(float(returns.mean()), 6),
        "sharpe": _sharpe(returns),
        "max_drawdown": _max_drawdown(returns),
        "ic": _information_coefficient(frame, returns),
        "ir": _information_coefficient(frame, returns),
        "standard_fields": list(STANDARD_REPORT_FIELDS),
    }


def write_benchmark_report(path: str | Path, output_path: str | Path) -> Path:
    report = build_benchmark_report(path)
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return destination


def _empty_benchmark(source: Path) -> dict[str, object]:
    return {
        "status": "empty",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_path": str(source),
        "qlib": qlib_status(),
        "sample_count": 0,
        "win_rate": None,
        "avg_return_3d": 0.0,
        "sharpe": None,
        "max_drawdown": None,
        "ic": None,
        "ir": None,
        "standard_fields": list(STANDARD_REPORT_FIELDS),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build an offline benchmark report.")
    parser.add_argument("--input", required=True, help="CSV/Parquet file exported from offline research.")
    parser.add_argument("--output", default="research/reports/benchmark.json")
    args = parser.parse_args()
    path = write_benchmark_report(args.input, args.output)
    print(f"report: {path}")


if __name__ == "__main__":
    main()
