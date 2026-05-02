from __future__ import annotations

import unittest

import pandas as pd

from app.services.low_buy.mainline_strength import candidate_mainline_info, rank_mainline_industries
from app.services.low_buy.shared import BoardCandidate


class MainlineStrengthTest(unittest.TestCase):
    def test_rank_prefers_persistent_pool_backed_mainline_over_pure_intraday_spike(self) -> None:
        live_frame = pd.DataFrame(
            [
                {"板块名称": "短线异动", "涨跌幅": 6.2},
                {"板块名称": "人工智能", "涨跌幅": 2.1},
                {"板块名称": "机器人", "涨跌幅": 1.8},
            ]
        )
        pooled_candidates = {
            "000001": BoardCandidate("000001", "A", "2026-04-26", 1, 260_000_000, "人工智能"),
            "000002": BoardCandidate("000002", "B", "2026-04-25", 1, 180_000_000, "人工智能"),
            "000003": BoardCandidate("000003", "C", "2026-04-26", 1, 150_000_000, "机器人"),
        }
        scores = rank_mainline_industries(
            live_frame=live_frame,
            pooled_candidates=pooled_candidates,
            latest_trade_date="2026-04-26",
            recent_sequences=[["人工智能", "机器人"], ["人工智能", "通信"], ["机器人", "人工智能"]],
        )

        self.assertGreaterEqual(len(scores), 3)
        self.assertEqual(scores[0].industry, "人工智能")
        self.assertEqual(scores[0].tier, "core_mainline")
        self.assertLess(scores[0].score, 101)

    def test_candidate_mainline_info_marks_core_leader(self) -> None:
        info = candidate_mainline_info(
            sector_name="人工智能",
            mainline_industries=["人工智能", "机器人"],
            leader_rank="leader",
        )

        self.assertEqual(info.rank, 1)
        self.assertEqual(info.tier, "core_mainline")
        self.assertEqual(info.tier_text, "核心主线")


if __name__ == "__main__":
    unittest.main()
