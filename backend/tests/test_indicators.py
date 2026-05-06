import math
import unittest

from app.models.schemas import KlineBar
from app.services.indicators import (
    atr,
    exponential_moving_average,
    macd,
    moving_average,
    rsi,
    sanitize_metrics,
    vwap,
)


class IndicatorSanitizeTests(unittest.TestCase):
    def test_ema_uses_sma_seed(self):
        self.assertEqual(exponential_moving_average([1, 2, 3, 4], 3), 3.0)

    def test_macd_uses_aligned_sma_seeded_ema_series(self):
        self.assertEqual(macd([float(i) for i in range(1, 41)]), (7.0, 7.0, 0.0))

    def test_moving_average_uses_latest_window(self):
        self.assertEqual(moving_average([1, 2, 3, 10], 3), 5.0)

    def test_rsi_returns_expected_extremes_and_neutral_short_series(self):
        self.assertEqual(rsi([1, 2, 3], 14), 50.0)
        self.assertEqual(rsi([float(i) for i in range(1, 17)], 14), 100.0)

    def test_atr_uses_true_range(self):
        bars = [
            KlineBar(timestamp=str(index), open=10, close=10 + index, high=12 + index, low=9 + index, volume=100, amount=1000)
            for index in range(16)
        ]
        self.assertEqual(atr(bars, 14), 3.0)

    def test_vwap_uses_typical_price_weighted_by_volume(self):
        bars = [
            KlineBar(timestamp="1", open=10, close=11, high=12, low=9, volume=100, amount=1000),
            KlineBar(timestamp="2", open=12, close=13, high=14, low=11, volume=300, amount=4000),
        ]
        self.assertEqual(vwap(bars), 12.1667)

    def test_sanitize_metrics_keeps_text_and_cleans_numbers(self):
        payload = sanitize_metrics(
            {
                "score": 12.34567,
                "bad_number": math.inf,
                "flag": True,
                "scene": "回踩承接",
            }
        )

        self.assertEqual(payload["score"], 12.3457)
        self.assertEqual(payload["bad_number"], 0.0)
        self.assertIs(payload["flag"], True)
        self.assertEqual(payload["scene"], "回踩承接")


if __name__ == "__main__":
    unittest.main()
