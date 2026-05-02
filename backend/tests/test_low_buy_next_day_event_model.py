from __future__ import annotations

import unittest

from app.services.low_buy.exit_plan import build_exit_plan
from app.services.low_buy.next_day_event_model import build_next_day_event_plan
from backend.tests.test_divergence_consensus_strategy import _item, _metrics
from app.services.low_buy.candidate_rules import build_strategy_setup
from backend.scripts.low_buy_market_backtest import TradeOutcome, _signal_group_stats


class LowBuyNextDayEventModelTests(unittest.TestCase):
    def test_limit_up_retrace_near_entry_uses_next_day_take_profit_plan(self) -> None:
        metrics = _metrics(
            platform_support_distance_pct=3.6,
            post_volume_ratio=0.86,
            latest_volume_ratio=0.78,
            distribution_risk_score=3.2,
            board_low_held=True,
            latest_close=9.82,
            platform_high=9.5,
        )

        plan = build_next_day_event_plan(
            strategy="limit_up_breakout_retrace",
            item=_item(amount=180_000_000),
            metrics=metrics,
            research_stage="near_entry",
        )

        self.assertEqual(plan.state, "take_profit_watch")
        self.assertEqual(plan.state_text, "次日冲高兑现")
        self.assertEqual(plan.first_take_profit_pct, 3.0)
        self.assertEqual(plan.second_take_profit_pct, 5.0)
        self.assertEqual(plan.max_holding_days, 2)
        self.assertIn("冲高 3%-5%", plan.next_day_action)
        self.assertTrue(any("VWAP" in rule for rule in plan.exit_rules))

    def test_divergence_consensus_buy_ready_still_only_allows_small_weak_to_strong_confirmation(self) -> None:
        metrics = _metrics(
            consensus_breakout=True,
            consensus_volume_ratio=1.68,
            consensus_close_strength=0.72,
            consolidation_volume_ratio=0.61,
            latest_close=10.42,
            divergence_high=10.25,
            distribution_risk_score=2.8,
            long_upper_shadow=False,
            weak_close=False,
        )

        plan = build_next_day_event_plan(
            strategy="divergence_consensus",
            item=_item(amount=260_000_000),
            metrics=metrics,
            research_stage="buy_ready",
        )

        self.assertEqual(plan.state, "weak_to_strong_candidate")
        self.assertEqual(plan.state_text, "弱转强候选")
        self.assertLessEqual(plan.position_pct, 12.0)
        self.assertEqual(plan.max_holding_days, 3)
        self.assertIn("T+2", plan.t2_action)
        self.assertTrue(any("分歧高点" in rule for rule in plan.confirmation_rules))

    def test_research_strategy_exit_plans_are_short_event_windows(self) -> None:
        metrics = _metrics()
        limit_setup = build_strategy_setup("limit_up_breakout_retrace", _item(), metrics, 91.0)
        divergence_setup = build_strategy_setup("divergence_consensus", _item(), metrics, 94.0)

        limit_plan = build_exit_plan(
            strategy="limit_up_breakout_retrace",
            metrics=metrics,
            setup=limit_setup,
            stop_loss=9.3,
            take_profit=10.8,
        )
        divergence_plan = build_exit_plan(
            strategy="divergence_consensus",
            metrics=metrics,
            setup=divergence_setup,
            stop_loss=9.6,
            take_profit=11.0,
        )

        self.assertEqual(limit_plan.max_holding_days, 2)
        self.assertEqual(divergence_plan.max_holding_days, 2)
        self.assertTrue(any("3%-5%" in rule for rule in limit_plan.exit_rules))
        self.assertTrue(any("次日" in rule for rule in divergence_plan.exit_rules))

    def test_backtest_stats_include_next_day_event_metrics(self) -> None:
        stats = _signal_group_stats(
            outcomes=[
                TradeOutcome(
                    symbol="300059",
                    name="东方财富",
                    signal_date="2026-04-01",
                    strategy_key="limit_up_breakout_retrace",
                    buy_signal_state="near_entry",
                    entry_price=10.0,
                    execution_status="filled",
                    net_return_pct=1.2,
                    execution_exit_reason="止盈",
                    return_1d=1.5,
                    return_2d=0.8,
                    return_3d=0.4,
                    return_4d=-0.1,
                    return_5d=-0.3,
                    max_gain_5d=4.2,
                    max_drawdown_5d=-1.1,
                    t1_high_return_pct=3.4,
                    t1_close_return_pct=0.4,
                    t1_spike_fade_pct=3.0,
                    t2_high_return_pct=2.2,
                    t2_close_return_pct=1.0,
                    t1_hit_3_pct=True,
                    t1_hit_5_pct=False,
                    t1_fade_to_entry=False,
                )
            ],
            states={"near_entry"},
            target_profit_pct=3.0,
        )

        self.assertEqual(stats["t1_high_3_hit_rate"], 100.0)
        self.assertEqual(stats["t1_high_5_hit_rate"], 0.0)
        self.assertEqual(stats["avg_t1_high_return_pct"], 3.4)
        self.assertEqual(stats["avg_t2_close_return_pct"], 1.0)


if __name__ == "__main__":
    unittest.main()
