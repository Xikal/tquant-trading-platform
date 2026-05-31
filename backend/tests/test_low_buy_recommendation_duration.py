from __future__ import annotations

import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.entities import LowBuyResultSnapshot, LowBuyScanSnapshot
from app.models.schemas import LowBuyCandidateOut
from app.services.low_buy.recommendation_duration import attach_recommendation_durations
from app.services.low_buy.priority_board import LowBuyPriorityBoardMixin
from app.services.low_buy.results import LowBuyResultStoreMixin
from app.services.low_buy.shared import LOW_BUY_RESULT_VERSION
from app.services.low_buy.strategy_policy import (
    participates_in_priority_board,
    strategy_layer,
    strong_buy_paused,
)


def _candidate(
    *,
    symbol: str = "000001",
    strategy_key: str = "first_board",
    signal_state: str = "buy_now",
) -> LowBuyCandidateOut:
    return LowBuyCandidateOut(
        strategy_key=strategy_key,
        strategy_title="首板回调" if strategy_key == "first_board" else strategy_key,
        payload_version=LOW_BUY_RESULT_VERSION,
        symbol=symbol,
        name="测试股份",
        market="SZ",
        instrument_type="stock",
        sector_name="机器人",
        latest_price=10.0,
        change_pct=1.0,
        quote_timestamp="2026-04-24 10:00:00",
        board_date="2026-04-20",
        board_count=1,
        retracement_days=3,
        score=90.0,
        entry_zone_low=9.8,
        entry_zone_high=10.1,
        stop_loss=9.5,
        take_profit=11.0,
        ma5=9.9,
        ma10=9.7,
        ma20=9.4,
        volume_burst_ratio=2.0,
        volume_shrink_ratio=0.62,
        support_distance_pct=1.2,
        execution_ready=True,
        execution_note="测试",
        suggested_position_pct=12.0,
        suggested_position_text="测试",
        summary_reason="测试",
        buy_signal_state=signal_state,  # type: ignore[arg-type]
        buy_signal_text="确定买入" if signal_state == "buy_now" else "继续观察",
        buy_signal_hint="测试",
        reasons=["测试"],
        risks=["测试"],
        tags=["测试"],
    )


class LowBuyRecommendationDurationTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine, future=True)

    def test_strategy_layers_follow_24_month_backtest_decision(self) -> None:
        self.assertTrue(participates_in_priority_board("first_board"))
        self.assertTrue(participates_in_priority_board("volume_shrink"))
        self.assertTrue(participates_in_priority_board("late_session_strong_support"))
        self.assertFalse(participates_in_priority_board("core_midcap_vwap_ma5_retrace"))
        self.assertFalse(participates_in_priority_board("sector_mainline_first_divergence_low_buy"))
        self.assertFalse(participates_in_priority_board("mainline_limitup_shrink_retrace_reclaim"))
        self.assertFalse(participates_in_priority_board("classic_retrace"))
        self.assertFalse(participates_in_priority_board("ma_support"))
        self.assertFalse(participates_in_priority_board("divergence_consensus"))
        self.assertEqual(strategy_layer("volume_shrink"), "production")
        self.assertEqual(strategy_layer("late_session_strong_support"), "production")
        self.assertEqual(strategy_layer("mainline_limitup_shrink_retrace_reclaim"), "research")
        self.assertTrue(strong_buy_paused("ma_support"))
        self.assertTrue(strong_buy_paused("classic_retrace"))
        self.assertTrue(strong_buy_paused("divergence_consensus"))
        self.assertTrue(strong_buy_paused("n_pattern_long_wash"))
        self.assertFalse(strong_buy_paused("first_board"))
        self.assertFalse(strong_buy_paused("volume_shrink"))

    def test_paused_strategy_strong_buy_is_downgraded_for_old_snapshots(self) -> None:
        candidate = _candidate(strategy_key="limit_up_breakout_retrace", signal_state="buy_now")
        normalized = LowBuyResultStoreMixin._normalize_candidate_policy_state(candidate)

        self.assertEqual(normalized.buy_signal_state, "near_entry")
        self.assertIn("观察层", normalized.buy_signal_hint)

    def test_recommendation_days_count_consecutive_actionable_snapshots(self) -> None:
        with self.Session() as db:
            for trade_date in ["2026-04-24", "2026-04-23", "2026-04-22", "2026-04-21"]:
                db.add(
                    LowBuyScanSnapshot(
                        latest_trade_date=trade_date,
                        strategy_key="first_board",
                        strategy_title="首板回调",
                        strategy_subtitle="测试",
                        strategy_logic="测试",
                        as_of_date=f"{trade_date} 15:00:00",
                        pool_size=10,
                        scanned_count=10,
                        matched_count=1,
                        requested_scan_limit=10,
                        active_scan_limit=10,
                        retracement_distribution_json="{}",
                        filters_json="{}",
                        strategy_notes_json="[]",
                    )
                )
            db.add_all(
                [
                    LowBuyResultSnapshot(
                        latest_trade_date="2026-04-23",
                        strategy_key="first_board",
                        symbol="000001",
                        name="测试股份",
                        score=90.0,
                        buy_signal_state="near_entry",
                        payload_json="{}",
                    ),
                    LowBuyResultSnapshot(
                        latest_trade_date="2026-04-22",
                        strategy_key="first_board",
                        symbol="000001",
                        name="测试股份",
                        score=90.0,
                        buy_signal_state="buy_now",
                        payload_json="{}",
                    ),
                    LowBuyResultSnapshot(
                        latest_trade_date="2026-04-21",
                        strategy_key="first_board",
                        symbol="000001",
                        name="测试股份",
                        score=90.0,
                        buy_signal_state="watch",
                        payload_json="{}",
                    ),
                ]
            )
            db.commit()

            enriched = attach_recommendation_durations(
                db=db,
                candidates=[
                    _candidate(symbol="000001", signal_state="buy_now"),
                    _candidate(symbol="000002", signal_state="near_entry"),
                    _candidate(symbol="000003", signal_state="watch"),
                ],
                latest_trade_date="2026-04-24",
            )

        by_symbol = {candidate.symbol: candidate for candidate in enriched}
        self.assertEqual(by_symbol["000001"].recommendation_days, 3)
        self.assertEqual(by_symbol["000001"].recommendation_start_date, "2026-04-22")
        self.assertIn("首板回调第 3 天", by_symbol["000001"].recommendation_duration_text)
        self.assertNotIn("连续推荐", by_symbol["000001"].recommendation_duration_text)
        self.assertEqual(by_symbol["000002"].recommendation_days, 1)
        self.assertEqual(by_symbol["000003"].recommendation_days, 0)

    def test_priority_duration_text_uses_single_plain_sentence(self) -> None:
        text = LowBuyPriorityBoardMixin._priority_recommendation_duration_text(
            candidate=_candidate(symbol="000001"),
            recommendation_days_by_title={"首板回调": 2, "均线支撑": 1},
        )

        self.assertIn("首板回调第 2 天", text)
        self.assertNotIn("连续推荐", text)
        self.assertEqual(text.count("推荐"), 0)


if __name__ == "__main__":
    unittest.main()
