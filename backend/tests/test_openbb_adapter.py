from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

import requests

from app.services.market.openbb_adapter import OpenBBDataAdapter


class OpenBBAdapterTests(unittest.TestCase):
    def test_quote_uses_short_timeout_and_parses_yahoo_payload(self) -> None:
        response = Mock()
        response.json.return_value = {
            "chart": {
                "result": [
                    {
                        "meta": {
                            "chartPreviousClose": 100,
                            "regularMarketPrice": 105,
                        }
                    }
                ]
            }
        }
        response.raise_for_status.return_value = None

        with patch("app.services.market.openbb_adapter.requests.get", return_value=response) as get:
            adapter = OpenBBDataAdapter()
            quote = adapter.quote("aapl")

        self.assertLessEqual(adapter.timeout, 3)
        self.assertEqual(quote.symbol, "AAPL")
        self.assertTrue(quote.available)
        self.assertEqual(quote.last_price, 105)
        self.assertEqual(quote.change_pct, 5)
        self.assertLessEqual(get.call_args.kwargs["timeout"], 3)

    def test_quote_failure_returns_empty_payload_without_raising(self) -> None:
        with patch(
            "app.services.market.openbb_adapter.requests.get",
            side_effect=requests.Timeout("too slow"),
        ):
            quote = OpenBBDataAdapter(timeout=1).quote("MSFT")

        self.assertEqual(quote.symbol, "MSFT")
        self.assertFalse(quote.available)
        self.assertEqual(quote.last_price, 0.0)
        self.assertIn("failed", quote.message.lower())

    def test_status_and_macro_status_are_best_effort(self) -> None:
        with patch(
            "app.services.market.openbb_adapter.requests.get",
            side_effect=requests.ConnectionError("offline"),
        ):
            adapter = OpenBBDataAdapter(timeout=1)
            status = adapter.status()
            macro = adapter.macro_status(["CPIAUCSL"])

        self.assertTrue(status["optional"])
        self.assertIn("quote", status["capabilities"])
        self.assertIn("macro_status", status["capabilities"])
        self.assertEqual(macro["status"], "degraded")
        self.assertEqual(macro["indicators"][0]["code"], "CPIAUCSL")
        self.assertIsNone(macro["indicators"][0]["latest_value"])


if __name__ == "__main__":
    unittest.main()
