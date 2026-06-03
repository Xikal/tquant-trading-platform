from __future__ import annotations

import unittest
from unittest.mock import patch

from app.core.timing import record_request_timing, request_timing_snapshot
from app.services.market.shared import QuoteSnapshot
from app.services.market.service import MarketDataService


class PerformanceRegressionTest(unittest.TestCase):
    def test_intraday_batch_preserves_symbols_without_network(self) -> None:
        service = MarketDataService()

        def fake_bars(symbol: str, period: str = "1m", limit: int = 30):  # noqa: ARG001
            return [symbol]

        service.get_intraday_bars = fake_bars  # type: ignore[method-assign]
        result = service.get_intraday_bars_batch(["000001", "000002", "000001"], max_workers=4)

        self.assertEqual(result["000001"], ["000001"])
        self.assertEqual(result["000002"], ["000002"])
        self.assertEqual(set(result), {"000001", "000002"})

    def test_quote_cache_returns_cached_payload_without_deep_copy(self) -> None:
        service = MarketDataService()
        quote = QuoteSnapshot(
            symbol="000001",
            name="平安银行",
            market="SZ",
            instrument_type="stock",
            last_price=10.0,
            change_pct=1.0,
            change_amount=0.1,
            open_price=9.9,
            high_price=10.2,
            low_price=9.8,
            prev_close=9.9,
            volume=1000,
            amount=100000,
            turnover_rate=None,
            volume_ratio=None,
            timestamp="2026-05-02 10:00:00",
        )
        service._set_quote_cache("000001", quote)

        self.assertIs(service._get_quote_cache("000001"), quote)

    def test_eastmoney_realtime_quote_parser_marks_source(self) -> None:
        service = MarketDataService()
        quote = service._build_eastmoney_realtime_quote_snapshot(
            "000001",
            {
                "f2": 11.49,
                "f3": -0.26,
                "f4": -0.03,
                "f5": 1139242,
                "f6": 1312827775.76,
                "f8": 0.59,
                "f10": 0.74,
                "f12": "000001",
                "f13": 0,
                "f14": "平安银行",
                "f15": 11.6,
                "f16": 11.46,
                "f17": 11.5,
                "f18": 11.52,
                "f124": 1777534458,
            },
        )

        self.assertEqual(quote.data_source, "eastmoney_realtime")
        self.assertEqual(quote.source_quality, "free_realtime")
        self.assertEqual(quote.name, "平安银行")
        self.assertEqual(quote.last_price, 11.49)

    def test_request_timing_snapshot_records_recent_samples(self) -> None:
        record_request_timing(method="GET", path="/api/test", status_code=200, duration_ms=120)
        snapshot = request_timing_snapshot()

        self.assertGreaterEqual(snapshot["sample_count"], 1)
        self.assertTrue(any(item["route"] == "GET /api/test" for item in snapshot["by_path"]))

    def test_prometheus_metrics_include_agent_tool_counters(self) -> None:
        from app.main import prometheus_metrics

        with patch(
            "app.main._agent_audit_metrics_snapshot",
            return_value={"calls_total": 2, "success_total": 1, "failure_total": 1},
        ):
            response = prometheus_metrics(None)

        body = response.body.decode("utf-8")
        self.assertIn("tquant_agent_tool_calls_total 2", body)
        self.assertIn("tquant_agent_tool_success_total 1", body)
        self.assertIn("tquant_agent_tool_failure_total 1", body)
        self.assertIn("tquant_bff_remote_calls_total", body)
        self.assertIn("tquant_bff_remote_failures_total", body)
        self.assertIn("tquant_rust_math_fallback_ratio_bps", body)
        self.assertIn("tquant_derived_indicator_cache_hits_total", body)
        self.assertIn("tquant_derived_indicator_cache_misses_total", body)
        self.assertIn("tquant_derived_indicator_cache_size", body)
        self.assertIn("tquant_runtime_task_duration_p95_ms", body)


if __name__ == "__main__":
    unittest.main()
