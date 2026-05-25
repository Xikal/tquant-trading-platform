from __future__ import annotations

import unittest
from decimal import Decimal


class PaperAutoConfirmationTests(unittest.TestCase):
    def test_auto_sized_order_never_requires_manual_confirmation(self) -> None:
        from app.services.paper.sizing import SizedOrder

        order = SizedOrder(
            symbol="510300",
            name="沪深300ETF",
            side="buy",
            order_type="market",
            quantity=100,
            price=Decimal("4.0"),
            current_price=Decimal("4.0"),
            strategy_key="sector_etf_t0",
            reason="自动交易测试",
            signal_snapshot={},
        )

        self.assertFalse(order.to_plan_dict()["require_intraday_confirmation"])


if __name__ == "__main__":
    unittest.main()
