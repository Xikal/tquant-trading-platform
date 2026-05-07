from __future__ import annotations

import unittest

from app.models.schemas import MicrostructureSnapshot, QuoteSnapshot, SectorSnapshot
from app.services.distribution_signals import DistributionSnapshot
from app.services.quant_engine_execution import (
    negative_buyback_allowed,
    negative_direction_gate,
    positive_direction_gate,
    risk_reward_metrics,
    trade_levels,
)


def _quote(**overrides) -> QuoteSnapshot:
    payload = {
        "symbol": "510300",
        "name": "沪深300ETF",
        "market": "SH",
        "instrument_type": "etf",
        "last_price": 10.05,
        "change_pct": 0.8,
        "change_amount": 0.08,
        "open_price": 9.98,
        "high_price": 10.18,
        "low_price": 9.88,
        "prev_close": 9.97,
        "volume": 1_000_000,
        "amount": 900_000_000,
        "timestamp": "2026-05-04T10:30:00",
    }
    payload.update(overrides)
    return QuoteSnapshot(**payload)


def _sector(**overrides) -> SectorSnapshot:
    payload = {
        "sector_name": "沪深300ETF",
        "sector_strength": 68.0,
        "market_strength": 62.0,
        "alignment_score": 72.0,
        "notes": "测试板块联动",
    }
    payload.update(overrides)
    return SectorSnapshot(**payload)


def _microstructure(**overrides) -> MicrostructureSnapshot:
    payload = {
        "available": True,
        "buy_pressure": 62.0,
        "sell_pressure": 58.0,
        "large_order_flow": 8.0,
        "notes": "测试盘口",
    }
    payload.update(overrides)
    return MicrostructureSnapshot(**payload)


def _distribution(**overrides) -> DistributionSnapshot:
    payload = {
        "upper_shadow_ratio": 0.12,
        "close_position_ratio": 0.72,
        "weak_close": False,
        "long_upper_shadow": False,
        "false_breakout_flag": False,
        "stall_after_volume_flag": False,
        "intraday_reversal_flag": False,
        "distribution_risk_score": 1.2,
    }
    payload.update(overrides)
    return DistributionSnapshot(**payload)


class QuantEngineExecutionTests(unittest.TestCase):
    def test_positive_gate_allows_confirmed_pullback_and_trade_levels_are_ordered(self) -> None:
        allowed, reason = positive_direction_gate(
            quote=_quote(),
            ma5=10.0,
            ma20=9.85,
            slope10=0.18,
            vwap_value=10.0,
            sector=_sector(),
            microstructure=_microstructure(),
            distribution=_distribution(),
            intraday_structure="pullback_acceptance",
        )
        self.assertTrue(allowed, reason)

        entry, exit_price, stop_loss, take_profit, expected_profit_pct = trade_levels(
            "positive_t",
            _quote(),
            vwap_value=10.0,
            ma5=10.0,
            atr_value=0.12,
            slippage_bps=4.0,
            max_single_loss_pct=1.0,
        )

        self.assertIsNotNone(entry)
        self.assertIsNotNone(exit_price)
        self.assertIsNotNone(stop_loss)
        self.assertEqual(exit_price, take_profit)
        self.assertGreater(exit_price, entry)
        self.assertLess(stop_loss, entry)
        self.assertGreater(expected_profit_pct, 0)

    def test_negative_gate_rejects_when_buyback_room_is_too_small(self) -> None:
        allowed, reason = negative_direction_gate(
            quote=_quote(last_price=10.03, high_price=10.06),
            ma5=10.0,
            rsi14=68.0,
            macd_hist=-0.03,
            vwap_value=10.0,
            amplitude=2.6,
            sector=_sector(),
            microstructure=_microstructure(sell_pressure=64.0),
            distribution=_distribution(),
            intraday_structure="overheat_exhaustion",
        )

        self.assertFalse(allowed)
        self.assertIn("接回空间不足", reason)

    def test_negative_trade_levels_require_buyback_below_vwap_or_ma5_anchor(self) -> None:
        quote = _quote(last_price=10.5, high_price=10.6, low_price=9.92)
        sell_price, buy_price, stop_loss, take_profit, expected_profit_pct = trade_levels(
            "negative_t",
            quote,
            vwap_value=10.15,
            ma5=10.2,
            atr_value=0.16,
            slippage_bps=4.0,
            max_single_loss_pct=1.0,
        )

        self.assertIsNotNone(sell_price)
        self.assertIsNotNone(buy_price)
        self.assertIsNotNone(stop_loss)
        self.assertEqual(buy_price, take_profit)
        self.assertGreater(sell_price, buy_price)
        self.assertGreater(stop_loss, sell_price)
        self.assertGreater(expected_profit_pct, 0)

        allowed, reason = negative_buyback_allowed(buy_price=10.25, vwap_value=10.15, ma5=10.2)
        self.assertFalse(allowed)
        self.assertIn("分时均价线或5日线下方", reason)

        ratio, loss_pct = risk_reward_metrics("negative_t", sell_price, buy_price, stop_loss)
        self.assertGreater(ratio, 0)
        self.assertGreater(loss_pct, 0)


if __name__ == "__main__":
    unittest.main()
