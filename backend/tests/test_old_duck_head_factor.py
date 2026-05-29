from __future__ import annotations

import unittest

from app.services.low_buy.candidate_types import CandidateMetrics
from app.services.low_buy.factor_functions import default_factor_weights, list_factor_specs
from app.services.low_buy.old_duck_head import (
    assess_old_duck_head_structure,
    enrich_old_duck_head_payload,
)
from app.services.low_buy.shared import BoardCandidate


def _item(**overrides) -> BoardCandidate:
    data = {
        "symbol": "000001",
        "name": "测试股份",
        "board_date": "2026-04-17",
        "board_count": 1,
        "amount": 260_000_000.0,
        "industry": "人工智能",
    }
    data.update(overrides)
    return BoardCandidate(**data)


def _metrics(**overrides) -> CandidateMetrics:
    data = {
        "latest_trade_date": "2026-04-24",
        "retracement_days": 9,
        "latest_open": 9.92,
        "latest_close": 10.12,
        "latest_high": 10.22,
        "latest_low": 9.86,
        "latest_change_pct": 1.6,
        "ma5": 10.02,
        "ma10": 9.82,
        "ma20": 9.48,
        "ma60": 8.92,
        "board_open": 9.12,
        "board_close": 10.03,
        "board_low": 9.08,
        "board_high": 10.05,
        "board_mid_price": 9.575,
        "board_gain_ok": True,
        "volume_burst_ratio": 2.35,
        "latest_volume_ratio": 0.82,
        "post_volume_ratio": 0.64,
        "shrink_staircase": True,
        "close_to_ma5": 0.8,
        "close_to_ma10": 3.1,
        "close_to_ma20": 6.75,
        "support_distance_pct": 0.75,
        "support_distance_ma20_pct": 6.75,
        "breakout_level": 9.5,
        "breakout_distance_pct": 6.53,
        "platform_high": 9.45,
        "platform_low": 8.86,
        "platform_window_days": 28,
        "platform_range_pct": 14.5,
        "platform_breakout_pct": 6.14,
        "platform_support_distance_pct": 7.09,
        "divergence_high": 10.25,
        "divergence_volume_ratio": 0.88,
        "divergence_day_stall": True,
        "consolidation_days": 4,
        "consolidation_low": 9.72,
        "consolidation_high": 10.18,
        "consolidation_volume_ratio": 0.54,
        "consensus_breakout": True,
        "consensus_volume_ratio": 1.72,
        "consensus_close_strength": 0.83,
        "recent_low_guard": 9.72,
        "recent_swing_high": 10.72,
        "drawdown_from_board_pct": 0.7,
        "latest_body_pct": 2.0,
        "upper_shadow_ratio": 0.12,
        "lower_shadow_ratio": 0.10,
        "close_position_ratio": 0.72,
        "doji_like": False,
        "long_lower_shadow": False,
        "long_upper_shadow": False,
        "weak_close": False,
        "false_breakout_flag": False,
        "stall_after_volume_flag": False,
        "intraday_reversal_flag": False,
        "distribution_risk_score": 2.4,
        "momentum_exhaustion": True,
        "trend_ok": True,
        "strong_trend": True,
        "support_ok": True,
        "shrink_ok": True,
        "shrink_basic_ok": True,
        "board_low_held": True,
        "board_open_held": True,
        "support_watch_ok": True,
        "latest_change_ok": True,
    }
    data.update(overrides)
    return CandidateMetrics(**data)


class OldDuckHeadFactorTests(unittest.TestCase):
    def test_supported_wash_structure_gets_factor_reason_and_tag(self) -> None:
        assessment = assess_old_duck_head_structure("n_pattern_long_wash", _item(), _metrics())

        self.assertTrue(assessment.matched)
        self.assertGreaterEqual(assessment.factor_score, 2.2)
        factor_scores, reasons, tags = enrich_old_duck_head_payload(
            {},
            ["原策略原因"],
            ["趋势筛选"],
            assessment,
        )

        self.assertEqual(factor_scores["old_duck_head_factor"], assessment.factor_score)
        self.assertIn("老鸭头", tags)
        self.assertTrue(any("老鸭头结构" in reason for reason in reasons))

    def test_distribution_or_reversal_risk_blocks_old_duck_head_factor(self) -> None:
        assessment = assess_old_duck_head_structure(
            "n_pattern_long_wash",
            _item(),
            _metrics(distribution_risk_score=6.2, intraday_reversal_flag=True),
        )

        self.assertFalse(assessment.matched)
        self.assertEqual(assessment.factor_score, 0.0)
        self.assertTrue(any("派发风险" in rule for rule in assessment.failed_rules))

    def test_unrelated_strategy_does_not_receive_old_duck_head_factor(self) -> None:
        assessment = assess_old_duck_head_structure("classic_retrace", _item(), _metrics())

        self.assertFalse(assessment.matched)
        self.assertEqual(assessment.factor_score, 0.0)

    def test_old_duck_head_factor_is_registered_with_default_weight(self) -> None:
        specs = {spec.name: spec for spec in list_factor_specs()}
        weights = default_factor_weights()

        self.assertIn("old_duck_head_factor", specs)
        self.assertIn("old_duck_head_factor", weights)
        self.assertGreater(weights["old_duck_head_factor"], 0.0)
        self.assertEqual(specs["old_duck_head_factor"].status, "active")


if __name__ == "__main__":
    unittest.main()
