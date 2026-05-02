from __future__ import annotations

import unittest

from app.models.schemas import LowBuyPriorityBoardItemOut
from app.services.low_buy.simple_decision import (
    build_daily_decision,
    build_simple_buckets,
    enrich_priority_item,
    market_plain_text,
)


class _Board:
    def __init__(
        self,
        *,
        market_state: str,
        immediate_count: int = 0,
        focus_count: int = 0,
        track_count: int = 0,
    ) -> None:
        self.market_state = market_state
        self.immediate_count = immediate_count
        self.focus_count = focus_count
        self.track_count = track_count


def _item(
    *,
    symbol: str = "000001",
    strategy_key: str = "first_board",
    signal_state: str = "buy_now",
) -> LowBuyPriorityBoardItemOut:
    return LowBuyPriorityBoardItemOut(
        symbol=symbol,
        name="样本股份",
        sector_name="机器人",
        strategy_key=strategy_key,
        strategy_title="首板回调",
        strategy_titles=["首板回调"],
        latest_price=10.0,
        change_pct=1.0,
        quote_timestamp="2026-04-29 10:00:00",
        buy_signal_state=signal_state,  # type: ignore[arg-type]
        buy_signal_text="确定可买" if signal_state == "buy_now" else "接近买点",
        priority_score=88.0,
        strategy_weight_score=80.0,
        industry_rotation_bonus=0.0,
        industry_rotation_text="",
        action_summary="测试",
        blocked_reason="",
        entry_zone_low=9.8,
        entry_zone_high=10.1,
        stop_loss=9.5,
        suggested_position_pct=12.0,
        suggested_position_text="先试 12%",
        recommendation_days=2,
    )


class LowBuySimpleDecisionTests(unittest.TestCase):
    def test_market_state_uses_plain_text(self) -> None:
        self.assertEqual(market_plain_text("weight_support"), "指数被权重托住，题材股别追高")
        self.assertEqual(market_plain_text("unknown"), "环境一般，小仓观察")

    def test_weight_support_maps_to_observe_only(self) -> None:
        decision = build_daily_decision(_Board(market_state="weight_support", focus_count=2))

        self.assertEqual(decision.key, "observe_only")
        self.assertIn("别追高", decision.market_plain_text)
        self.assertIn("不追高", decision.action_steps)

    def test_broad_rally_with_immediate_signal_maps_to_tradable(self) -> None:
        decision = build_daily_decision(_Board(market_state="broad_rally", immediate_count=1))

        self.assertEqual(decision.key, "tradable")
        self.assertIn("小仓", decision.message)

    def test_high_flyer_retreat_blocks_new_buy(self) -> None:
        decision = build_daily_decision(_Board(market_state="high_flyer_retreat", immediate_count=3))

        self.assertEqual(decision.key, "wait")
        self.assertEqual(decision.risk_level, "high")

    def test_buy_now_near_entry_and_watch_bucketed_separately(self) -> None:
        buckets = build_simple_buckets(
            [
                enrich_priority_item(_item(symbol="000001", signal_state="buy_now")),
                enrich_priority_item(_item(symbol="000002", signal_state="near_entry")),
                enrich_priority_item(_item(symbol="000003", signal_state="watch")),
            ]
        )

        by_key = {bucket.key: bucket for bucket in buckets}
        self.assertEqual(by_key["buy_now"].title, "确定可买")
        self.assertEqual(by_key["wait_price"].symbols, ["000002"])
        self.assertEqual(by_key["give_up"].symbols, ["000003"])

    def test_observation_strategy_strong_buy_is_not_bucketed_as_buy_now(self) -> None:
        item = enrich_priority_item(_item(strategy_key="limit_up_breakout_retrace", signal_state="buy_now"))

        self.assertEqual(item.simple_bucket, "give_up")
        self.assertEqual(item.simple_bucket_text, "放弃观察")
        self.assertTrue(item.next_action_text)
        self.assertIn("第 2 天", item.recommendation_duration_text)


if __name__ == "__main__":
    unittest.main()
