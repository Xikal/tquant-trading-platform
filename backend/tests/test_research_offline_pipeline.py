from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from research.backtest.benchmark import build_benchmark_report, write_benchmark_report
from research.backtest.strategy_validation import build_strategy_validation_report
from research.data_sync.tquant_to_qlib import export_daily_bars, qlib_status, read_offline_table


class OfflineResearchPipelineTests(unittest.TestCase):
    def test_export_daily_bars_writes_readable_offline_file_without_pyarrow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "bars.sqlite"
            output_dir = Path(tmp) / "datasets"
            with sqlite3.connect(db_path) as conn:
                conn.execute(
                    """
                    CREATE TABLE daily_bar_snapshots (
                        symbol TEXT,
                        trade_date TEXT,
                        open REAL,
                        high REAL,
                        low REAL,
                        close REAL,
                        volume REAL,
                        amount REAL
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT INTO daily_bar_snapshots
                    VALUES ('000001.SZ', '2026-01-02', 10, 11, 9.5, 10.8, 1200, 12960)
                    """
                )

            exported = export_daily_bars(f"sqlite:///{db_path}", output_dir)
            self.assertTrue(exported.exists())
            self.assertIn(exported.suffix, {".parquet", ".csv"})
            frame = read_offline_table(exported)
            self.assertEqual(len(frame), 1)
            self.assertEqual(frame.loc[0, "symbol"], "000001.SZ")

    def test_qlib_status_is_optional_and_never_import_crashes(self) -> None:
        status = qlib_status()
        self.assertIn("available", status)
        self.assertIn("message", status)
        self.assertIsInstance(status["available"], bool)

    def test_strategy_validation_outputs_standard_empty_report_for_missing_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = build_strategy_validation_report(
                Path(tmp) / "missing.csv",
                strategy_keys=["auxiliary_alpha"],
            )

        self.assertEqual(report["status"], "empty")
        self.assertEqual(report["reports"][0]["strategy_key"], "auxiliary_alpha")
        self.assertEqual(report["reports"][0]["sample_count"], 0)
        for field in ("ic", "ir", "sharpe", "max_drawdown", "win_rate"):
            self.assertIn(field, report["reports"][0])

    def test_strategy_validation_calculates_standard_metrics_from_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "signals.csv"
            pd.DataFrame(
                [
                    {
                        "strategy_key": "auxiliary_alpha",
                        "trade_date": "2026-01-02",
                        "factor_score": 0.2,
                        "return_3d": 0.01,
                        "forward_return_1d": 0.02,
                    },
                    {
                        "strategy_key": "auxiliary_alpha",
                        "trade_date": "2026-01-03",
                        "factor_score": 0.1,
                        "return_3d": -0.02,
                        "forward_return_1d": -0.01,
                    },
                    {
                        "strategy_key": "auxiliary_alpha",
                        "trade_date": "2026-01-04",
                        "factor_score": 0.3,
                        "return_3d": 0.03,
                        "forward_return_1d": 0.04,
                    },
                ]
            ).to_csv(input_path, index=False)

            report = build_strategy_validation_report(input_path, strategy_keys=["auxiliary_alpha"])

        summary = report["reports"][0]
        self.assertEqual(report["status"], "ok")
        self.assertEqual(summary["sample_count"], 3)
        self.assertEqual(summary["win_rate"], 66.67)
        self.assertEqual(summary["max_drawdown"], 0.02)
        self.assertGreater(summary["sharpe"], 0)
        self.assertIsNotNone(summary["ic"])
        self.assertIsNotNone(summary["ir"])

    def test_benchmark_report_can_be_written_for_empty_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "empty.csv"
            output_path = Path(tmp) / "benchmark.json"
            pd.DataFrame(columns=["strategy_key", "return_3d"]).to_csv(input_path, index=False)

            report = build_benchmark_report(input_path)
            written = write_benchmark_report(input_path, output_path)

            self.assertEqual(report["status"], "empty")
            self.assertEqual(written, output_path)
            payload = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["sample_count"], 0)
        for field in ("ic", "ir", "sharpe", "max_drawdown", "win_rate"):
            self.assertIn(field, payload)


if __name__ == "__main__":
    unittest.main()
