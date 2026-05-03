from __future__ import annotations

import unittest

from app.models.schemas import LowBuyCandidateOut, LowBuyPriorityBoardResponse
from app.services.low_buy.base_strategy import get_low_buy_strategy, list_low_buy_strategies
from app.services.low_buy.data_quality import (
    build_candidate_data_quality,
    build_market_data_quality,
)
from app.services.market.state_categories import standard_market_state_key, standard_market_state_label


class LowBuyStandardizationTest(unittest.TestCase):
    def test_base_strategy_adapter_wraps_existing_playbooks(self) -> None:
        strategy = get_low_buy_strategy("first_board")

        self.assertEqual(strategy.identity.key, "first_board")
        self.assertEqual(strategy.identity.title, "首板回调")
        self.assertTrue(strategy.participates_priority_board)
        self.assertTrue(any(item.key == "first_board" for item in list_low_buy_strategies()))

    def test_market_states_are_normalized_to_six_categories(self) -> None:
        self.assertEqual(standard_market_state_key("broad_rally"), "broad_rally")
        self.assertEqual(standard_market_state_key("repair"), "repair")
        self.assertEqual(standard_market_state_key("weight_support_active"), "weight_support")
        self.assertEqual(standard_market_state_key("low_volume_wait"), "low_volume_wait")
        self.assertEqual(standard_market_state_key("fast_rotation"), "fast_rotation")
        self.assertEqual(standard_market_state_key("risk_release"), "risk_retreat")
        self.assertEqual(standard_market_state_label("high_flyer_retreat"), "退潮/风险释放")

    def test_data_quality_tags_degrade_without_market_inputs(self) -> None:
        market_quality = build_market_data_quality(
            breadth_ready=False,
            emotion_ready=False,
            hot_industry_source="unavailable",
        )
        self.assertEqual(market_quality.quality, "limited")
        self.assertIn("热点数据回退", market_quality.tags)

        candidate_quality = build_candidate_data_quality(
            latest_price=0,
            quote_timestamp="",
            market_quality=market_quality,
        )
        self.assertEqual(candidate_quality.quality, "unavailable")
        self.assertIn("价格无效", candidate_quality.tags)

    def test_schema_defaults_keep_old_payloads_compatible(self) -> None:
        candidate = LowBuyCandidateOut(
            strategy_key="first_board",
            strategy_title="首板回调",
            symbol="000001",
            name="平安银行",
            market="SZ",
            instrument_type="stock",
            latest_price=10.0,
            change_pct=0.0,
            quote_timestamp="2026-05-03",
            board_date="2026-05-02",
            board_count=1,
            retracement_days=2,
            score=80.0,
            entry_zone_low=9.8,
            entry_zone_high=10.1,
            stop_loss=9.5,
            take_profit=10.8,
            ma5=10.0,
            ma10=9.9,
            ma20=9.8,
            volume_burst_ratio=1.8,
            volume_shrink_ratio=0.8,
            support_distance_pct=0.5,
            execution_ready=False,
            execution_note="观察",
            reasons=[],
            risks=[],
            tags=[],
        )

        self.assertEqual(candidate.data_quality, "ok")
        self.assertEqual(candidate.market_state_category, "low_volume_wait")

        response = LowBuyPriorityBoardResponse(
            as_of_date="2026-05-03 10:00:00",
            latest_trade_date="2026-05-03",
            updated_at="2026-05-03 10:00:00",
        )
        self.assertEqual(response.data_quality, "ok")
        self.assertEqual(response.market_state_category_text, "缩量观望")


if __name__ == "__main__":
    unittest.main()
