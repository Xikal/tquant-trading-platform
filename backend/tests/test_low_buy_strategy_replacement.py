from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.entities import DailyBarSnapshot, Instrument
from app.services.low_buy.candidate_rules import build_strategy_setup, passes_strategy_prefilter
from app.services.low_buy.exit_plan import build_exit_plan
from app.services.low_buy.pool import LowBuyPoolMixin
from app.services.low_buy.shared import DEFAULT_PRODUCTION_LOW_BUY_STRATEGY, PLAYBOOKS, normalize_low_buy_strategy
from app.services.low_buy.strategy_pool_n_pattern import n_pattern_anchor_matches, n_pattern_latest_bar_matches
from app.services.low_buy.strategy_policy import (
    StrategyTier,
    get_strategy_tier,
    mainline_industry_allowed,
    participates_in_priority_board,
    requires_mainline_industry,
    strategy_layer,
    strong_buy_paused,
)
from app.services.low_buy.strategy_pool_config import strategy_pool_key, strategy_uses_daily_scan_pool
from backend.tests.test_divergence_consensus_strategy import _item, _metrics


class LowBuyStrategyReplacementTests(unittest.TestCase):
    def test_strategy_slots_follow_replacement_plan(self) -> None:
        production = {
            "first_board",
            "volume_shrink",
            "late_session_strong_support",
        }
        demoted = {
            "classic_retrace",
            "ma_support",
            "breakout_support",
            "divergence_consensus",
            "trend_rebound",
            "deep_pullback",
            "limit_up_breakout_retrace",
            "n_pattern_long_wash",
            "n_pattern_short_wash",
            "core_midcap_vwap_ma5_retrace",
            "sector_mainline_first_divergence_low_buy",
            "mainline_limitup_shrink_retrace_reclaim",
        }

        for strategy in production:
            self.assertIn(strategy, PLAYBOOKS)
            self.assertTrue(participates_in_priority_board(strategy), strategy)
            self.assertFalse(strong_buy_paused(strategy), strategy)
        for strategy in demoted:
            self.assertFalse(participates_in_priority_board(strategy), strategy)
        self.assertEqual(strategy_layer("deep_pullback"), "research")
        self.assertEqual(strategy_layer("core_midcap_vwap_ma5_retrace"), "research")
        self.assertEqual(strategy_layer("mainline_limitup_shrink_retrace_reclaim"), "research")
        self.assertTrue(requires_mainline_industry("core_midcap_vwap_ma5_retrace"))
        self.assertTrue(requires_mainline_industry("mainline_limitup_shrink_retrace_reclaim"))
        self.assertEqual(DEFAULT_PRODUCTION_LOW_BUY_STRATEGY, "first_board")
        self.assertEqual(normalize_low_buy_strategy(None), "first_board")

    def test_mainline_strategies_require_available_hot_industry_data(self) -> None:
        strategy = "sector_mainline_first_divergence_low_buy"

        self.assertFalse(mainline_industry_allowed(strategy, "人工智能", []))
        self.assertFalse(mainline_industry_allowed(strategy, "", ["人工智能"]))
        self.assertFalse(mainline_industry_allowed(strategy, "半导体", ["人工智能"]))
        self.assertTrue(mainline_industry_allowed(strategy, "人工智能", ["人工智能"]))
        self.assertTrue(mainline_industry_allowed("first_board", "", []))

    def test_user_visible_new_strategy_names_match_intraday_confirmation(self) -> None:
        self.assertIn("分时均价", PLAYBOOKS["late_session_strong_support"]["logic"])
        self.assertIn("VWAP", PLAYBOOKS["core_midcap_vwap_ma5_retrace"]["title"])
        self.assertIn("分时均价", PLAYBOOKS["core_midcap_vwap_ma5_retrace"]["logic"])

    def test_new_strategy_pool_profiles_are_not_the_legacy_default_pool(self) -> None:
        pool = LowBuyPoolMixin()

        self.assertEqual(pool._strategy_board_window_days("first_board"), 10)
        self.assertGreater(pool._strategy_board_window_days("late_session_strong_support"), 10)
        self.assertGreater(pool._strategy_board_window_days("core_midcap_vwap_ma5_retrace"), 10)
        self.assertGreater(pool._strategy_board_window_days("sector_mainline_first_divergence_low_buy"), 10)
        self.assertGreater(pool._strategy_board_window_days("mainline_limitup_shrink_retrace_reclaim"), 10)
        self.assertGreater(pool._strategy_retracement_days_max("late_session_strong_support"), 7)
        self.assertIn("主线", pool._strategy_pool_profile_text("sector_mainline_first_divergence_low_buy"))
        self.assertIn("涨停", pool._strategy_pool_profile_text("mainline_limitup_shrink_retrace_reclaim"))
        self.assertEqual(strategy_pool_key("first_board"), "limit_up_event_pool")
        self.assertEqual(strategy_pool_key("volume_shrink"), "volume_contract_pool")
        self.assertEqual(strategy_pool_key("mainline_limitup_shrink_retrace_reclaim"), "mainline_limitup_retrace_pool")
        self.assertEqual(strategy_pool_key("classic_retrace"), "legacy_research_pool")
        self.assertTrue(strategy_uses_daily_scan_pool("core_midcap_vwap_ma5_retrace"))
        self.assertTrue(strategy_uses_daily_scan_pool("mainline_limitup_shrink_retrace_reclaim"))
        self.assertTrue(strategy_uses_daily_scan_pool("n_pattern_long_wash"))
        self.assertTrue(strategy_uses_daily_scan_pool("n_pattern_short_wash"))
        self.assertEqual(strategy_pool_key("n_pattern_long_wash"), "n_pattern_long_wash_pool")
        self.assertEqual(strategy_pool_key("n_pattern_short_wash"), "n_pattern_short_wash_pool")

    def test_mainline_strategy_scan_targets_are_filtered_before_history_loading(self) -> None:
        pool = LowBuyPoolMixin()
        targets = [
            _item(symbol="300001", industry="人工智能"),
            _item(symbol="300002", industry="半导体"),
            _item(symbol="300003", industry=""),
        ]

        filtered = pool._prepare_strategy_scan_targets(
            strategy="core_midcap_vwap_ma5_retrace",
            scan_targets=targets,
            hot_industries=["人工智能"],
        )

        self.assertEqual([item.symbol for item in filtered], ["300001"])
        self.assertEqual(
            pool._prepare_strategy_scan_targets(
                strategy="core_midcap_vwap_ma5_retrace",
                scan_targets=targets,
                hot_industries=[],
            ),
            [],
        )
        self.assertEqual(
            len(
                pool._prepare_strategy_scan_targets(
                    strategy="first_board",
                    scan_targets=targets,
                    hot_industries=[],
                )
            ),
            3,
        )

    def test_core_midcap_strategy_uses_local_daily_mainline_pool(self) -> None:
        engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine, future=True)
        pool = LowBuyPoolMixin()
        trade_dates = [f"2026-04-{day:02d}" for day in range(13, 28)]
        with Session() as db:
            db.add(Instrument(symbol="300001", name="主线中军", instrument_type="stock", sector_name="人工智能"))
            for index, trade_date in enumerate(trade_dates):
                pct_chg = 4.8 if trade_date == "2026-04-23" else (-1.2 if trade_date == "2026-04-27" else 0.6)
                volume = 2_000_000 if trade_date == "2026-04-23" else 1_200_000
                db.add(
                    DailyBarSnapshot(
                        symbol="300001",
                        trade_date=trade_date,
                        open_price=10 + index * 0.02,
                        close_price=10.1 + index * 0.02,
                        high_price=10.3 + index * 0.02,
                        low_price=9.9 + index * 0.02,
                        volume=volume,
                        amount=320_000_000,
                        pct_chg=pct_chg,
                    )
                )
            db.commit()

            candidates = pool._load_strategy_scan_pool(
                db=db,
                strategy="core_midcap_vwap_ma5_retrace",
                latest_trade_date="2026-04-27",
                scan_limit=12,
                hot_industries=["人工智能"],
            )

        self.assertIsNotNone(candidates)
        self.assertEqual([item.symbol for item in candidates or []], ["300001"])
        self.assertEqual((candidates or [])[0].board_date, "2026-04-23")

    def test_late_session_strategy_is_next_day_event_trade(self) -> None:
        item = _item(amount=260_000_000)
        metrics = _metrics(
            retracement_days=2,
            latest_change_pct=2.4,
            close_position_ratio=0.72,
            support_distance_pct=1.8,
            close_to_ma5=1.1,
            latest_volume_ratio=0.92,
            post_volume_ratio=0.84,
            long_upper_shadow=False,
            weak_close=False,
            distribution_risk_score=2.6,
        )

        self.assertTrue(passes_strategy_prefilter("late_session_strong_support", item, metrics))
        setup = build_strategy_setup("late_session_strong_support", item, metrics, 88.0)
        plan = build_exit_plan(
            strategy="late_session_strong_support",
            metrics=metrics,
            setup=setup,
            stop_loss=9.8,
            take_profit=10.8,
        )

        self.assertTrue(setup.execution_ready)
        self.assertEqual(plan.max_holding_days, 2)
        self.assertTrue(any("次日" in rule for rule in plan.exit_rules))

    def test_core_midcap_strategy_requires_large_liquid_trend_retrace(self) -> None:
        item = _item(amount=620_000_000)
        metrics = _metrics(
            retracement_days=2,
            latest_change_pct=-1.8,
            close_to_ma5=1.0,
            close_to_ma10=1.4,
            support_distance_pct=1.0,
            latest_close=10.03,
            ma5=9.96,
            ma10=9.82,
            latest_volume_ratio=0.82,
            post_volume_ratio=0.88,
            trend_ok=True,
            strong_trend=True,
            false_breakout_flag=False,
            distribution_risk_score=2.8,
        )

        self.assertTrue(passes_strategy_prefilter("core_midcap_vwap_ma5_retrace", item, metrics))
        setup = build_strategy_setup("core_midcap_vwap_ma5_retrace", item, metrics, 87.0)

        self.assertTrue(setup.execution_ready)
        self.assertIn("中军", setup.summary_reason)

    def test_sector_mainline_first_divergence_strategy_uses_light_first_divergence_entry(self) -> None:
        item = _item(amount=320_000_000)
        metrics = _metrics(
            retracement_days=2,
            latest_change_pct=-2.6,
            close_to_ma5=1.3,
            support_distance_pct=1.3,
            latest_volume_ratio=1.05,
            post_volume_ratio=1.04,
            board_low_held=True,
            distribution_risk_score=3.0,
            long_upper_shadow=False,
            weak_close=False,
        )

        self.assertTrue(passes_strategy_prefilter("sector_mainline_first_divergence_low_buy", item, metrics))
        setup = build_strategy_setup("sector_mainline_first_divergence_low_buy", item, metrics, 84.0)

        self.assertTrue(setup.execution_ready)
        self.assertIn("首分歧", setup.summary_reason)

    def test_mainline_limitup_retrace_waits_for_shrink_and_ma5_reclaim(self) -> None:
        item = _item(amount=360_000_000, industry="半导体")
        metrics = _metrics(
            retracement_days=5,
            latest_change_pct=1.2,
            latest_close=10.08,
            latest_high=10.16,
            latest_low=9.92,
            ma5=10.03,
            ma10=9.96,
            ma20=9.88,
            close_to_ma5=0.50,
            close_to_ma10=1.20,
            close_to_ma20=2.02,
            support_distance_pct=1.2,
            volume_burst_ratio=2.1,
            latest_volume_ratio=0.82,
            post_volume_ratio=0.58,
            board_low_held=True,
            distribution_risk_score=2.8,
            long_upper_shadow=False,
            weak_close=False,
            false_breakout_flag=False,
            intraday_reversal_flag=False,
            recent_low_guard=9.86,
        )

        strategy = "mainline_limitup_shrink_retrace_reclaim"
        self.assertTrue(passes_strategy_prefilter(strategy, item, metrics))
        setup = build_strategy_setup(strategy, item, metrics, 90.0)

        self.assertTrue(setup.execution_ready)
        self.assertIn("缩量回调", setup.summary_reason)
        self.assertIn("不追高", setup.execution_note)

        chasing_metrics = _metrics(
            retracement_days=5,
            latest_change_pct=5.4,
            latest_close=10.42,
            ma5=10.03,
            ma10=9.96,
            ma20=9.88,
            close_to_ma5=3.89,
            support_distance_pct=3.89,
            volume_burst_ratio=2.1,
            latest_volume_ratio=0.82,
            post_volume_ratio=0.58,
            board_low_held=True,
            distribution_risk_score=2.8,
        )

        self.assertFalse(passes_strategy_prefilter(strategy, item, chasing_metrics))

        double_bottom_metrics = _metrics(
            retracement_days=6,
            latest_change_pct=0.8,
            latest_close=10.12,
            ma5=10.04,
            ma10=9.82,
            ma20=9.54,
            close_to_ma5=0.80,
            close_to_ma10=3.05,
            close_to_ma20=6.08,
            support_distance_pct=1.4,
            support_touch_count=2,
            volume_burst_ratio=2.2,
            latest_volume_ratio=0.86,
            post_volume_ratio=0.62,
            board_low_held=True,
            distribution_risk_score=2.6,
            recent_low_guard=9.88,
        )

        self.assertTrue(passes_strategy_prefilter(strategy, item, double_bottom_metrics))

    def test_n_pattern_strategies_are_research_and_use_launch_low_guard(self) -> None:
        item = _item(amount=220_000_000)
        long_metrics = _metrics(
            retracement_days=10,
            latest_change_pct=1.4,
            close_position_ratio=0.68,
            close_to_ma10=2.0,
            close_to_ma20=2.4,
            support_distance_pct=2.0,
            volume_burst_ratio=1.8,
            latest_volume_ratio=0.86,
            post_volume_ratio=0.58,
            board_low_held=True,
            distribution_risk_score=2.8,
            false_breakout_flag=False,
            intraday_reversal_flag=False,
        )
        short_metrics = _metrics(
            retracement_days=3,
            latest_change_pct=0.8,
            close_position_ratio=0.62,
            support_distance_pct=2.6,
            volume_burst_ratio=1.6,
            latest_volume_ratio=0.82,
            post_volume_ratio=0.82,
            board_low_held=True,
            doji_like=True,
            long_lower_shadow=True,
            long_upper_shadow=False,
            distribution_risk_score=2.6,
            false_breakout_flag=False,
        )

        for strategy, metrics in (
            ("n_pattern_long_wash", long_metrics),
            ("n_pattern_short_wash", short_metrics),
        ):
            with self.subTest(strategy=strategy):
                self.assertEqual(strategy_layer(strategy), "research")
                self.assertEqual(get_strategy_tier(strategy), StrategyTier.RESEARCH)
                self.assertTrue(strong_buy_paused(strategy))
                self.assertFalse(participates_in_priority_board(strategy))
                self.assertTrue(passes_strategy_prefilter(strategy, item, metrics))
                setup = build_strategy_setup(strategy, item, metrics, 88.0)
                self.assertTrue(setup.execution_ready)
                self.assertIn("N 字", setup.execution_note)

        broken_low_metrics = long_metrics.__class__(**{**long_metrics.__dict__, "board_low_held": False})
        self.assertFalse(passes_strategy_prefilter("n_pattern_long_wash", item, broken_low_metrics))

    def test_short_wash_requires_reversal_candle_not_generic_momentum_exhaustion(self) -> None:
        item = _item(amount=220_000_000)
        metrics = _metrics(
            retracement_days=3,
            latest_change_pct=0.8,
            close_position_ratio=0.62,
            support_distance_pct=2.6,
            volume_burst_ratio=1.6,
            latest_volume_ratio=0.82,
            board_low_held=True,
            doji_like=False,
            long_lower_shadow=False,
            momentum_exhaustion=True,
            long_upper_shadow=False,
            distribution_risk_score=2.6,
            false_breakout_flag=False,
        )

        self.assertFalse(passes_strategy_prefilter("n_pattern_short_wash", item, metrics))
        setup = build_strategy_setup("n_pattern_short_wash", item, metrics, 88.0)
        self.assertFalse(setup.execution_ready)

    def test_n_pattern_daily_pool_thresholds_follow_parameter_config(self) -> None:
        latest_bar = SimpleNamespace(
            amount=90_000_000,
            pct_chg=1.2,
            high_price=10.8,
            low_price=10.0,
            close_price=10.6,
        )
        anchor = SimpleNamespace(
            amount=160_000_000,
            volume=2_000_000,
            pct_chg=7.2,
            open_price=10.0,
            close_price=10.8,
            high_price=11.0,
            low_price=9.8,
        )
        prior_rows = [SimpleNamespace(volume=1_000_000), SimpleNamespace(volume=1_100_000)]
        strict_params = {
            "min_amount": 120_000_000.0,
            "latest_bar_min_change_pct": -3.5,
            "latest_bar_max_change_pct": 6.8,
            "latest_bar_min_close_position_ratio": 0.45,
            "anchor_min_pct_chg": 8.0,
            "anchor_min_close_open_ratio": 1.08,
            "anchor_min_volume_ratio": 2.5,
            "anchor_min_close_position_ratio": 0.72,
        }

        with patch(
            "app.services.low_buy.strategy_pool_n_pattern.prefilter_params",
            return_value=strict_params,
        ):
            self.assertFalse(n_pattern_latest_bar_matches("n_pattern_long_wash", latest_bar))
            self.assertFalse(n_pattern_anchor_matches("n_pattern_long_wash", anchor, prior_rows))


if __name__ == "__main__":
    unittest.main()
