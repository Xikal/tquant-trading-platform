from __future__ import annotations

import os
import unittest
from datetime import datetime


class PaperAutoTradingRuntimeConfigTest(unittest.TestCase):
    def test_auto_trader_trading_time(self):
        from app.services.paper.scheduler import PaperAutoTrader

        trader = PaperAutoTrader({})
        self.assertFalse(trader._is_trading_time(datetime(2026, 5, 2, 10, 0)))
        self.assertFalse(trader._is_trading_time(datetime(2026, 5, 4, 10, 0)))
        self.assertTrue(trader._is_trading_time(datetime(2026, 5, 6, 10, 0)))
        self.assertFalse(trader._is_trading_time(datetime(2026, 5, 6, 15, 0)))

    def test_auto_trader_state_init(self):
        from app.services.paper.scheduler import PaperAutoTrader

        trader = PaperAutoTrader(
            {
                "dry_run": True,
                "interval_seconds": 120,
                "max_orders_per_cycle": 5,
                "min_score": 75,
            }
        )
        self.assertTrue(trader.state.dry_run)
        self.assertFalse(trader.state.running)
        self.assertEqual(trader.state.interval_seconds, 120)
        self.assertEqual(trader.state.max_orders_per_cycle, 5)
        self.assertEqual(trader.state.min_score, 75)

    def test_config_defaults(self):
        from app.core.config import get_settings

        original_enabled = os.environ.get("PAPER_AUTO_TRADING_ENABLED")
        original_dry_run = os.environ.get("PAPER_AUTO_TRADING_DRY_RUN")
        os.environ["PAPER_AUTO_TRADING_ENABLED"] = "true"
        os.environ["PAPER_AUTO_TRADING_DRY_RUN"] = "false"
        get_settings.cache_clear()
        try:
            settings = get_settings()
            self.assertTrue(settings.paper_auto_trading_enabled)
            self.assertFalse(settings.paper_auto_trading_dry_run)
        finally:
            if original_enabled is None:
                os.environ.pop("PAPER_AUTO_TRADING_ENABLED", None)
            else:
                os.environ["PAPER_AUTO_TRADING_ENABLED"] = original_enabled
            if original_dry_run is None:
                os.environ.pop("PAPER_AUTO_TRADING_DRY_RUN", None)
            else:
                os.environ["PAPER_AUTO_TRADING_DRY_RUN"] = original_dry_run
            get_settings.cache_clear()

    def test_module_trading_time_helper(self):
        from app.services.paper.scheduler import is_trading_time

        self.assertFalse(is_trading_time(datetime(2026, 5, 2, 10, 0)))
        self.assertFalse(is_trading_time(datetime(2026, 5, 4, 10, 0)))
        self.assertTrue(is_trading_time(datetime(2026, 5, 6, 10, 0)))
        self.assertFalse(is_trading_time(datetime(2026, 5, 6, 15, 0)))


if __name__ == "__main__":
    unittest.main()
