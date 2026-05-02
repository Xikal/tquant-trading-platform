from __future__ import annotations

import unittest

from app.services.market.intraday_router import IntradaySourceRouter
from app.services.market.quote_router import QuoteSourceRouter


class QuoteRouterTests(unittest.TestCase):
    def test_fetch_uses_first_successful_loader(self) -> None:
        class Service:
            def _fetch_quote_from_spot_snapshot(self, symbol):
                raise RuntimeError("spot down")

            def _fetch_quote_from_minute_bars(self, symbol):
                return {"symbol": symbol, "source": "minute"}

            def _fetch_tencent_quote(self, symbol):
                raise AssertionError("should not continue after success")

            _fetch_quote_from_trends = _fetch_tencent_quote
            _fetch_eastmoney_quote = _fetch_tencent_quote
            _fetch_sina_quote = _fetch_tencent_quote

        router = QuoteSourceRouter(Service())
        snapshot = router.fetch("000001")
        self.assertEqual(snapshot["source"], "minute")

    def test_batch_falls_back_to_single_fetch(self) -> None:
        class Service:
            def _fetch_tencent_quotes_batch(self, symbols):
                return {"000001": {"symbol": "000001", "source": "batch"}}

            def _fetch_quote_from_spot_snapshot(self, symbol):
                return {"symbol": symbol, "source": "single"}

            _fetch_quote_from_minute_bars = _fetch_quote_from_spot_snapshot
            _fetch_tencent_quote = _fetch_quote_from_spot_snapshot
            _fetch_quote_from_trends = _fetch_quote_from_spot_snapshot
            _fetch_eastmoney_quote = _fetch_quote_from_spot_snapshot
            _fetch_sina_quote = _fetch_quote_from_spot_snapshot

        router = QuoteSourceRouter(Service())
        result = router.fetch_batch(["000001", "000002"])
        self.assertEqual(result["000001"]["source"], "batch")
        self.assertEqual(result["000002"]["source"], "single")


class IntradayRouterTests(unittest.TestCase):
    def test_loads_from_first_available_source(self) -> None:
        class Service:
            ak_available = False

            def _fetch_trend_bars(self, symbol):
                raise RuntimeError("trends down")

            def _fetch_tencent_minute_bars(self, symbol):
                return [{"symbol": symbol, "source": "tencent"}]

        router = IntradaySourceRouter(Service())
        bars = router.load_one_minute_bars("000001")
        self.assertEqual(bars[0]["source"], "tencent")

    def test_uses_ak_fallback_when_enabled(self) -> None:
        class Service:
            ak_available = True

            def _fetch_trend_bars(self, symbol):
                raise RuntimeError("trends down")

            def _fetch_tencent_minute_bars(self, symbol):
                raise RuntimeError("tencent down")

            def _fetch_sina_minute_bars(self, symbol, period):
                return [{"symbol": symbol, "source": "sina"}]

            def _fetch_sina_minute_bars_subprocess(self, symbol):
                raise AssertionError("should not use subprocess after sina success")

        router = IntradaySourceRouter(Service())
        bars = router.load_one_minute_bars("000001")
        self.assertEqual(bars[0]["source"], "sina")


if __name__ == "__main__":
    unittest.main()
