from __future__ import annotations

import unittest

from app.services.low_buy.factor_functions import default_factor_weights, list_factor_specs


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
        self.assertTrue(specs["sector_flow_factor"].status_text)


if __name__ == "__main__":
    unittest.main()
