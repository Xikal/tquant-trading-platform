from __future__ import annotations

import unittest
from types import SimpleNamespace

from app.services.low_buy.factor_functions import (
    default_factor_weights,
    evaluate_registered_external_factors,
    list_factor_specs,
)
from app.services.low_buy.candidate_types import CandidateMetrics
from app.services.low_buy.factor_scoring import build_factor_scores
from app.services.low_buy.factor_types import FactorContext
from app.services.low_buy.selection_quality_factor import evaluate_selection_quality_factor


def _metrics():
    common = {
        "latest_trade_date": "2026-05-29",
        "retracement_days": 2,
        "latest_open": 10.0,
        "latest_close": 9.8,
        "latest_high": 10.2,
        "latest_low": 9.6,
        "latest_change_pct": -1.0,
        "ma5": 10.0,
        "ma10": 10.2,
        "ma20": 10.5,
        "ma60": 11.0,
        "board_open": 9.0,
        "board_close": 10.0,
        "board_low": 8.8,
        "board_high": 10.0,
        "board_mid_price": 9.5,
        "board_gain_ok": True,
        "volume_burst_ratio": 2.0,
        "latest_volume_ratio": 0.7,
        "post_volume_ratio": 0.6,
        "shrink_staircase": True,
        "close_to_ma5": 2.0,
        "close_to_ma10": 4.0,
        "close_to_ma20": 6.0,
        "support_distance_pct": 2.0,
        "support_distance_ma20_pct": 6.0,
        "breakout_level": 10.6,
        "breakout_distance_pct": 8.0,
        "platform_high": 10.8,
        "platform_low": 9.4,
        "platform_window_days": 10,
        "platform_range_pct": 12.0,
        "platform_breakout_pct": 0.0,
        "platform_support_distance_pct": 4.0,
        "divergence_high": 10.5,
        "divergence_volume_ratio": 1.0,
        "divergence_day_stall": False,
        "consolidation_days": 3,
        "consolidation_low": 9.5,
        "consolidation_high": 10.2,
        "consolidation_volume_ratio": 0.8,
        "consensus_breakout": False,
        "consensus_volume_ratio": 1.0,
        "consensus_close_strength": 0.5,
        "recent_low_guard": 9.4,
        "recent_swing_high": 10.8,
        "drawdown_from_board_pct": 8.0,
        "latest_body_pct": 1.0,
        "upper_shadow_ratio": 0.2,
        "lower_shadow_ratio": 0.4,
        "close_position_ratio": 0.6,
        "doji_like": False,
        "long_lower_shadow": False,
        "long_upper_shadow": False,
        "weak_close": False,
        "false_breakout_flag": False,
        "stall_after_volume_flag": False,
        "intraday_reversal_flag": False,
        "distribution_risk_score": 1.0,
        "momentum_exhaustion": False,
        "trend_ok": True,
        "strong_trend": False,
        "support_ok": True,
        "shrink_ok": True,
        "shrink_basic_ok": True,
        "board_low_held": True,
        "board_open_held": True,
        "support_watch_ok": True,
        "latest_change_ok": True,
        "shrink_quality_score": 0.0,
        "shrink_volatility": 0.2,
        "abnormal_volume_days": 0,
        "retracement_atr": 0.25,
        "retracement_atr_trend": 0.0,
    }
    return CandidateMetrics(**common)


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
        self.assertEqual(specs["north_flow_factor"].status, "experimental")
        self.assertEqual(specs["dragon_board_factor"].activation_condition, "realtime_only_no_backtest")
        self.assertEqual(specs["selection_quality_factor"].status, "active")
        self.assertEqual(specs["margin_balance_factor"].status, "stub")
        self.assertTrue(specs["sector_flow_factor"].status_text)

    def test_unavailable_stub_factors_default_to_zero_weight(self) -> None:
        weights = default_factor_weights()
        self.assertEqual(weights["pre_market_auction_factor"], 0.0)
        self.assertEqual(weights["margin_balance_factor"], 0.0)
        self.assertEqual(weights["block_trade_premium_factor"], 0.0)
        self.assertEqual(weights["earnings_surprise_factor"], 0.0)
        self.assertEqual(weights["insider_trade_factor"], 0.0)
        self.assertEqual(weights["short_balance_factor"], 0.0)

    def test_realtime_external_factors_are_blocked_without_context_permission(self) -> None:
        metrics = _metrics()
        context = FactorContext(
            current_symbol="603459",
            current_date="2026-05-29",
            confirmed_trade_date="2026-05-29",
            allow_realtime_external_factors=False,
        )

        scores = evaluate_registered_external_factors(metrics, context)

        self.assertNotIn("north_flow_factor", scores)
        self.assertNotIn("dragon_board_factor", scores)
        self.assertNotIn("limit_up_quality_factor", scores)

    def test_realtime_external_factors_are_allowed_only_with_context_permission(self) -> None:
        metrics = _metrics()
        context = FactorContext(
            current_symbol="603459",
            current_date="2026-05-29",
            confirmed_trade_date="2026-05-29",
            allow_realtime_external_factors=True,
        )

        scores = evaluate_registered_external_factors(metrics, context)

        self.assertIn("north_flow_factor", scores)
        self.assertIn("dragon_board_factor", scores)
        self.assertIn("limit_up_quality_factor", scores)

    def test_backtest_factor_scores_do_not_fetch_realtime_external_factors(self) -> None:
        scores = build_factor_scores(_metrics(), None)

        self.assertNotIn("north_flow_factor", scores)
        self.assertNotIn("dragon_board_factor", scores)
        self.assertNotIn("limit_up_quality_factor", scores)
        self.assertNotIn("big_order_flow_factor", scores)
        self.assertNotIn("event_risk_factor", scores)

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

    def test_selection_quality_blocks_false_breakout_and_stall(self) -> None:
        common = {
            "shrink_staircase": True,
            "post_volume_ratio": 0.6,
            "latest_volume_ratio": 0.7,
            "volume_burst_ratio": 2.4,
            "board_gain_ok": True,
            "distribution_risk_score": 1.0,
            "stall_after_volume_flag": False,
            "ma20": 100.0,
            "latest_close": 94.0,
            "close_to_ma20": 6.0,
        }

        false_breakout = SimpleNamespace(**{**common, "false_breakout_flag": True})
        stall_after_volume = SimpleNamespace(
            **{**common, "false_breakout_flag": False, "stall_after_volume_flag": True}
        )

        self.assertEqual(evaluate_selection_quality_factor(false_breakout), 0.0)
        self.assertEqual(evaluate_selection_quality_factor(stall_after_volume), 0.0)


if __name__ == "__main__":
    unittest.main()
