from __future__ import annotations

import unittest

from app.models.schemas import KlineBar
from app.services.low_buy.intraday_confirmation import (
    build_intraday_confirmation,
    calculate_intraday_vwap,
    intraday_confirmation_hint,
    intraday_confirmation_passes,
)


def _bar(
    timestamp: str,
    open_price: float,
    close: float,
    low: float,
    high: float,
    volume: float = 1000,
    amount: float | None = None,
) -> KlineBar:
    return KlineBar(
        timestamp=timestamp,
        open=open_price,
        close=close,
        low=low,
        high=high,
        volume=volume,
        amount=close * volume if amount is None else amount,
    )


class LowBuyIntradayConfirmationTests(unittest.TestCase):
    def test_vwap_uses_amount_when_available(self) -> None:
        bars = [
            _bar("2026-04-30 10:00", 10.00, 10.00, 9.80, 10.20, volume=100, amount=1_020),
            _bar("2026-04-30 10:01", 10.00, 10.00, 9.80, 10.20, volume=300, amount=3_150),
        ]

        self.assertEqual(calculate_intraday_vwap(bars), 10.425)

    def test_vwap_falls_back_per_bar_when_amount_is_missing(self) -> None:
        bars = [
            _bar("2026-04-30 10:00", 10.00, 10.00, 9.80, 10.20, volume=100, amount=1_020),
            _bar("2026-04-30 10:01", 11.00, 11.00, 10.80, 11.20, volume=100, amount=0),
        ]

        self.assertEqual(calculate_intraday_vwap(bars), 10.6)

    def test_vwap_normalizes_hand_volume_amount_units(self) -> None:
        bars = [
            _bar("2026-04-30 10:00", 10.00, 10.00, 9.80, 10.20, volume=100, amount=102_000),
            _bar("2026-04-30 10:01", 10.00, 10.00, 9.80, 10.20, volume=300, amount=315_000),
        ]

        self.assertEqual(calculate_intraday_vwap(bars), 10.425)

    def test_vwap_reclaim_confirms_core_midcap_strategy(self) -> None:
        bars = [
            _bar("2026-04-30 10:00", 10.00, 9.96, 9.94, 10.01),
            _bar("2026-04-30 10:01", 9.96, 9.98, 9.95, 10.00),
            _bar("2026-04-30 10:02", 9.98, 10.02, 9.97, 10.04),
            _bar("2026-04-30 10:03", 10.02, 10.05, 9.99, 10.06),
            _bar("2026-04-30 10:04", 10.05, 10.08, 10.01, 10.09),
        ]

        confirmation = build_intraday_confirmation(bars)

        self.assertTrue(intraday_confirmation_passes("core_midcap_vwap_ma5_retrace", confirmation))
        self.assertTrue(confirmation.above_vwap)
        self.assertTrue(confirmation.confirmed)

    def test_below_vwap_keeps_mainline_strategy_in_observation(self) -> None:
        bars = [
            _bar("2026-04-30 10:00", 10.10, 10.05, 10.04, 10.12),
            _bar("2026-04-30 10:01", 10.05, 10.02, 10.00, 10.07),
            _bar("2026-04-30 10:02", 10.02, 9.98, 9.96, 10.03),
            _bar("2026-04-30 10:03", 9.98, 9.95, 9.93, 10.00),
            _bar("2026-04-30 10:04", 9.95, 9.92, 9.90, 9.97),
        ]

        confirmation = build_intraday_confirmation(bars)

        self.assertFalse(intraday_confirmation_passes("sector_mainline_first_divergence_low_buy", confirmation))
        self.assertIn("分时均价", intraday_confirmation_hint("sector_mainline_first_divergence_low_buy", confirmation))

    def test_late_session_strength_confirms_close_support_strategy(self) -> None:
        bars = [
            _bar("2026-04-30 14:30", 10.00, 10.03, 9.99, 10.04),
            _bar("2026-04-30 14:31", 10.03, 10.05, 10.02, 10.06),
            _bar("2026-04-30 14:32", 10.05, 10.08, 10.04, 10.09),
            _bar("2026-04-30 14:33", 10.08, 10.10, 10.06, 10.11),
            _bar("2026-04-30 14:34", 10.10, 10.12, 10.08, 10.13),
        ]

        confirmation = build_intraday_confirmation(bars)

        self.assertTrue(intraday_confirmation_passes("late_session_strong_support", confirmation))
        self.assertTrue(confirmation.late_confirmed)

    def test_late_session_missing_low_does_not_raise(self) -> None:
        bars = [
            _bar("2026-04-30 14:30", 10.00, 10.03, 0.0, 10.04),
            _bar("2026-04-30 14:31", 10.03, 10.05, 0.0, 10.06),
            _bar("2026-04-30 14:32", 10.05, 10.08, 0.0, 10.09),
            _bar("2026-04-30 14:33", 10.08, 10.10, 0.0, 10.11),
            _bar("2026-04-30 14:34", 10.10, 10.12, 0.0, 10.13),
        ]

        confirmation = build_intraday_confirmation(bars)

        self.assertFalse(confirmation.late_confirmed)


if __name__ == "__main__":
    unittest.main()
