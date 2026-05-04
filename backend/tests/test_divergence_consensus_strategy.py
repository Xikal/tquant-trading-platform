from __future__ import annotations

import unittest

import pandas as pd

from app.services.low_buy.candidate_metrics import build_candidate_metrics
from app.services.low_buy.candidate_rules import build_strategy_setup, passes_strategy_prefilter, score_candidate
from app.services.low_buy.candidate_types import CandidateMetrics
from app.services.low_buy.research_layers import evaluate_research_layer
from app.services.low_buy.risk_tiers import resolve_low_buy_risk_tier
from app.services.low_buy.shared import BoardCandidate, PLAYBOOKS
from app.services.low_buy.signals import LowBuySignalMixin
from app.services.low_buy.strategy_families import resolve_strategy_family


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
        "retracement_days": 6,
        "latest_open": 10.18,
        "latest_close": 10.58,
        "latest_high": 10.72,
        "latest_low": 10.12,
        "latest_change_pct": 3.8,
        "ma5": 10.05,
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
        "latest_volume_ratio": 0.92,
        "post_volume_ratio": 0.64,
        "shrink_staircase": False,
        "close_to_ma5": 5.67,
        "close_to_ma10": 8.15,
        "close_to_ma20": 12.03,
        "support_distance_pct": 5.67,
        "support_distance_ma20_pct": 12.03,
        "breakout_level": 9.5,
        "breakout_distance_pct": 11.79,
        "platform_high": 9.45,
        "platform_low": 8.86,
        "platform_window_days": 28,
        "platform_range_pct": 14.5,
        "platform_breakout_pct": 6.14,
        "platform_support_distance_pct": 12.38,
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
        "drawdown_from_board_pct": 5.88,
        "latest_body_pct": 4.32,
        "upper_shadow_ratio": 0.17,
        "lower_shadow_ratio": 0.10,
        "close_position_ratio": 0.83,
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
        "support_ok": False,
        "shrink_ok": True,
        "shrink_basic_ok": True,
        "board_low_held": True,
        "board_open_held": True,
        "support_watch_ok": True,
        "latest_change_ok": True,
    }
    data.update(overrides)
    return CandidateMetrics(**data)


class DivergenceConsensusStrategyTests(unittest.TestCase):
    def test_strategy_is_registered_as_independent_playbook(self) -> None:
        self.assertIn("divergence_consensus", PLAYBOOKS)
        self.assertEqual(resolve_strategy_family("divergence_consensus"), "main_wave_confirmation")

    def test_strict_breakout_setup_passes_only_after_consensus_breakout(self) -> None:
        item = _item()
        metrics = _metrics()

        self.assertTrue(passes_strategy_prefilter("divergence_consensus", item, metrics))
        score = score_candidate("divergence_consensus", item, metrics, ["人工智能"])
        setup = build_strategy_setup("divergence_consensus", item, metrics, score)

        self.assertGreaterEqual(score, 90.0)
        self.assertTrue(setup.execution_ready)
        self.assertLessEqual(setup.entry_zone_low, metrics.divergence_high)
        self.assertGreaterEqual(setup.entry_zone_high, metrics.divergence_high)
        self.assertIn("突破分歧高点", setup.summary_reason)

    def test_loose_or_unconfirmed_setup_stays_in_research_layer(self) -> None:
        item = _item()
        loose_metrics = _metrics(consolidation_volume_ratio=0.86)
        failed_metrics = _metrics(consensus_breakout=False, latest_close=10.18)
        no_stall_metrics = _metrics(divergence_day_stall=False)
        no_settlement_metrics = _metrics(consolidation_days=0)

        self.assertTrue(passes_strategy_prefilter("divergence_consensus", item, loose_metrics))
        self.assertTrue(passes_strategy_prefilter("divergence_consensus", item, failed_metrics))
        self.assertFalse(
            build_strategy_setup("divergence_consensus", item, failed_metrics, 91.0).execution_ready
        )
        self.assertEqual(evaluate_research_layer("divergence_consensus", item, failed_metrics).stage, "near_entry")
        self.assertFalse(passes_strategy_prefilter("divergence_consensus", item, no_stall_metrics))
        self.assertFalse(passes_strategy_prefilter("divergence_consensus", item, no_settlement_metrics))

    def test_false_breakout_is_strictly_blocked(self) -> None:
        decision = resolve_low_buy_risk_tier(
            strategy="divergence_consensus",
            metrics=_metrics(false_breakout_flag=True, distribution_risk_score=3.6),
            market_regime=None,
        )

        self.assertEqual(decision.risk_tier, "block")
        self.assertTrue(decision.execution_blocked)

    def test_signal_allows_near_breakout_zone_for_research_tracking(self) -> None:
        mixin = LowBuySignalMixin()

        self.assertIn("in_zone", mixin._near_entry_positions("divergence_consensus"))
        self.assertIn("near_above_zone", mixin._near_entry_positions("divergence_consensus"))
        self.assertFalse(mixin._should_avoid_on_entry_position("divergence_consensus", "below_zone"))

    def test_metric_builder_does_not_backfill_missing_consolidation(self) -> None:
        history = _history_with_divergence_right_before_breakout()
        metrics = build_candidate_metrics(
            item=_item(board_date="2026-03-18"),
            latest_trade_date="2026-03-24",
            history=history,
        )

        self.assertIsNotNone(metrics)
        assert metrics is not None
        self.assertEqual(metrics.consolidation_days, 0)
        self.assertFalse(passes_strategy_prefilter("divergence_consensus", _item(), metrics))

    def test_limit_up_retrace_can_enter_observation_before_strict_buy(self) -> None:
        item = _item(amount=190_000_000)
        metrics = _metrics(
            retracement_days=1,
            latest_close=9.82,
            platform_high=9.50,
            platform_support_distance_pct=4.2,
            volume_burst_ratio=1.55,
            platform_breakout_pct=1.2,
            platform_range_pct=32.0,
            drawdown_from_board_pct=-1.5,
            post_volume_ratio=0.92,
            latest_volume_ratio=0.88,
            board_low_held=True,
        )

        self.assertTrue(passes_strategy_prefilter("limit_up_breakout_retrace", item, metrics))
        setup = build_strategy_setup("limit_up_breakout_retrace", item, metrics, 89.0)
        layer = evaluate_research_layer("limit_up_breakout_retrace", item, metrics)

        self.assertFalse(setup.execution_ready)
        self.assertEqual(layer.stage, "watch")
        self.assertTrue(layer.failed_rules)


def _history_with_divergence_right_before_breakout() -> pd.DataFrame:
    dates = pd.bdate_range("2026-01-01", periods=60).strftime("%Y-%m-%d").tolist()
    rows = []
    for index, trade_date in enumerate(dates):
        close = 8.8 + index * 0.01
        rows.append(
            {
                "date": trade_date,
                "open": close * 0.995,
                "high": close * 1.01,
                "low": close * 0.99,
                "close": close,
                "pct_chg": 0.2,
                "volume": 1_000_000.0,
                "ma5": close * 0.995,
                "ma10": close * 0.99,
                "ma20": close * 0.975,
                "ma60": close * 0.94,
            }
        )
    board_index = 54
    divergence_index = 58
    latest_index = 59
    rows[board_index].update(
        {
            "date": "2026-03-18",
            "open": 9.1,
            "high": 10.1,
            "low": 9.05,
            "close": 10.0,
            "pct_chg": 10.0,
            "volume": 3_000_000.0,
            "ma5": 9.5,
            "ma10": 9.35,
            "ma20": 9.1,
            "ma60": 8.8,
        }
    )
    rows[divergence_index].update(
        {
            "open": 10.15,
            "high": 10.5,
            "low": 9.95,
            "close": 10.22,
            "pct_chg": 2.0,
            "volume": 2_600_000.0,
            "ma5": 10.0,
            "ma10": 9.7,
            "ma20": 9.3,
            "ma60": 8.9,
        }
    )
    rows[latest_index].update(
        {
            "open": 10.28,
            "high": 10.92,
            "low": 10.22,
            "close": 10.78,
            "pct_chg": 5.5,
            "volume": 4_000_000.0,
            "ma5": 10.15,
            "ma10": 9.82,
            "ma20": 9.42,
            "ma60": 8.96,
        }
    )
    return pd.DataFrame(rows)


if __name__ == "__main__":
    unittest.main()
