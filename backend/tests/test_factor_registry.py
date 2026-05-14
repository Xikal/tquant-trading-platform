from __future__ import annotations

import unittest
from types import SimpleNamespace

from app.services.low_buy.factor_functions import default_factor_weights, list_factor_specs
from app.services.low_buy.selection_quality_factor import evaluate_selection_quality_factor


class FactorRegistryTests(unittest.TestCase):
    def test_new_optional_factors_are_registered(self) -> None:
        names = {item.name for item in list_factor_specs()}
        expected = {
            "north_flow_factor",
            "dragon_board_factor",
            "limit_up_quality_factor",
            "pre_market_auction_factor",
            "margin_balance_factor",
            "block_trade_premium_factor",
            "earnings_surprise_factor",
            "insider_trade_factor",
            "short_balance_factor",
        }
        self.assertTrue(expected.issubset(names))

    def test_registered_factors_have_default_weights(self) -> None:
        weights = default_factor_weights()
        self.assertIn("north_flow_factor", weights)
        self.assertIn("short_balance_factor", weights)
        self.assertGreaterEqual(weights["north_flow_factor"], 0.0)

    def test_factor_specs_expose_runtime_status(self) -> None:
        specs = {item.name: item for item in list_factor_specs()}
        self.assertEqual(specs["sector_flow_factor"].status, "experimental")
        self.assertEqual(specs["north_flow_factor"].status, "stub")
        self.assertEqual(specs["selection_quality_factor"].status, "active")
        self.assertTrue(specs["sector_flow_factor"].status_text)

    def test_selection_quality_requires_signed_ma20_pullback(self) -> None:
        common = {
            "shrink_staircase": False,
            "post_volume_ratio": 1.0,
            "latest_volume_ratio": 1.0,
            "volume_burst_ratio": 0.0,
            "board_gain_ok": False,
            "distribution_risk_score": 9.0,
            "false_breakout_flag": False,
            "stall_after_volume_flag": False,
            "ma20": 100.0,
            "close_to_ma20": 6.0,
        }

        above_ma20 = SimpleNamespace(**{**common, "latest_close": 106.0})
        below_ma20 = SimpleNamespace(**{**common, "latest_close": 94.0})

        self.assertEqual(evaluate_selection_quality_factor(above_ma20), 0.0)
        self.assertGreater(evaluate_selection_quality_factor(below_ma20), 0.0)


if __name__ == "__main__":
    unittest.main()
