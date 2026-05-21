import math
import unittest

from app.models.schemas import KlineBar
from app.services.indicators import (
    atr,
    bollinger_bands,
    exponential_moving_average,
    macd,
    macd_with_validity,
    moving_average,
    rsi,
    rsi_wilder,
    sanitize_metrics,
    stochastic,
    vwap,
    intraday_amplitude,
)


class IndicatorSanitizeTests(unittest.TestCase):
    def test_ema_uses_sma_seed(self):
        self.assertEqual(exponential_moving_average([1, 2, 3, 4], 3), 3.0)

    def test_macd_uses_aligned_sma_seeded_ema_series(self):
        self.assertEqual(macd([float(i) for i in range(1, 41)]), (7.0, 7.0, 0.0))

    def test_macd_marks_insufficient_data_invalid(self):
        self.assertEqual(macd_with_validity([1.0, 2.0, 3.0]), (0.0, 0.0, 0.0, False))

    def test_moving_average_uses_latest_window(self):
        self.assertEqual(moving_average([1, 2, 3, 10], 3), 5.0)

    def test_rsi_returns_expected_extremes_and_neutral_short_series(self):
        self.assertEqual(rsi([1, 2, 3], 14), 50.0)
        self.assertEqual(rsi([float(i) for i in range(1, 17)], 14), 100.0)
        self.assertEqual(rsi_wilder([float(i) for i in range(1, 17)], 14), 100.0)

    def test_atr_uses_true_range(self):
        bars = [
            KlineBar(timestamp=str(index), open=10, close=10 + index, high=12 + index, low=9 + index, volume=100, amount=1000)
            for index in range(28)
        ]
        self.assertEqual(atr(bars, 14), 3.0)

    def test_atr_returns_none_for_short_series(self):
        bars = [
            KlineBar(timestamp=str(index), open=10, close=10 + index, high=12 + index, low=9 + index, volume=100, amount=1000)
            for index in range(16)
        ]
        self.assertIsNone(atr(bars, 14))

    def test_bollinger_bands_use_sample_standard_deviation(self):
        upper, middle, lower = bollinger_bands([1, 2, 3, 4, 5], window=5, num_std=2)

        self.assertEqual(middle, 3.0)
        self.assertAlmostEqual(upper, 6.1623, places=4)
        self.assertAlmostEqual(lower, -0.1623, places=4)

    def test_stochastic_uses_configurable_d_sma(self):
        bars = [
            KlineBar(timestamp=str(index), open=5, close=close, high=high, low=low, volume=100, amount=1000)
            for index, (high, low, close) in enumerate(
                [(10, 0, 5), (11, 1, 6), (12, 2, 8), (13, 3, 10), (14, 4, 12)]
            )
        ]

        k_value, d_value = stochastic(bars, k_period=3, d_period=3)

        self.assertAlmostEqual(k_value, 83.3333, places=4)
        self.assertAlmostEqual(d_value, 75.0, places=4)

    def test_intraday_amplitude_uses_explicit_previous_close(self):
        bars = [
            KlineBar(timestamp="1", open=11, close=12, high=12, low=10, volume=100, amount=1000),
            KlineBar(timestamp="2", open=12, close=13, high=13, low=11, volume=100, amount=1000),
        ]
        self.assertEqual(intraday_amplitude(bars, prev_close=10), 30.0)

    def test_vwap_uses_typical_price_weighted_by_volume(self):
        bars = [
            KlineBar(timestamp="1", open=10, close=11, high=12, low=9, volume=100, amount=1000),
            KlineBar(timestamp="2", open=12, close=13, high=14, low=11, volume=300, amount=4000),
        ]
        self.assertEqual(vwap(bars), 12.1667)

    def test_vwap_resets_to_latest_trading_day(self):
        bars = [
            KlineBar(timestamp="2026-05-18 14:58:00", open=100, close=100, high=100, low=100, volume=10000, amount=1000000),
            KlineBar(timestamp="2026-05-19 09:31:00", open=10, close=11, high=12, low=9, volume=100, amount=1000),
            KlineBar(timestamp="2026-05-19 09:32:00", open=12, close=13, high=14, low=11, volume=300, amount=4000),
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
