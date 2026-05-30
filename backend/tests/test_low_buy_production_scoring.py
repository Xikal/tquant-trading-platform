from __future__ import annotations

import unittest

from app.models.schemas import LowBuyHardRiskOut
from app.services.low_buy.production_scoring import score_low_buy_candidate_for_production
from test_priority_weighting import _candidate


class LowBuyProductionScoringTests(unittest.TestCase):
    def test_near_entry_has_no_production_score_and_keeps_watch_score(self) -> None:
        candidate = _front_row_candidate().model_copy(update={"buy_signal_state": "near_entry"})

        result = score_low_buy_candidate_for_production(candidate)

        self.assertIsNone(result.production_score)
        self.assertIsNotNone(result.watch_score)
        self.assertEqual(result.decision, "watch_only")
        self.assertIn("near_entry_watch_only", result.warning_tags)

    def test_soft_buy_now_scores_above_same_condition_buy_now(self) -> None:
        buy_now = _candidate("classic_retrace").model_copy(
            update={
                "buy_signal_state": "buy_now",
                "leader_rank": "unknown",
                "industry_tier": "neutral",
                "mainline_tier": "unknown",
                "market_state": "repair",
                "entry_distance_pct": 1.8,
                "execution_ready": True,
                "distribution_risk_score": 2.0,
            }
        )
        soft_buy_now = buy_now.model_copy(update={"buy_signal_state": "soft_buy_now"})

        buy_result = score_low_buy_candidate_for_production(buy_now)
        soft_result = score_low_buy_candidate_for_production(soft_buy_now)

        self.assertIsNotNone(buy_result.production_score)
        self.assertIsNotNone(soft_result.production_score)
        self.assertGreater(soft_result.production_score, buy_result.production_score)

    def test_laggard_caps_score_to_68(self) -> None:
        candidate = _front_row_candidate().model_copy(
            update={
                "leader_rank": "laggard",
                "industry_tier": "neutral",
                "mainline_tier": "unknown",
                "market_state": "repair",
                "score": 99.0,
                "leader_strength_rank": 0,
                "leader_strength_score": 0.0,
                "multi_timeframe_resonance_score": 20.0,
            }
        )

        result = score_low_buy_candidate_for_production(candidate)

        self.assertEqual(result.front_row_tier, "laggard")
        self.assertEqual(result.score_cap, 68.0)
        self.assertLessEqual(result.production_score or 0.0, 68.0)

    def test_weak_market_laggard_caps_score_to_55(self) -> None:
        candidate = _front_row_candidate().model_copy(
            update={
                "leader_rank": "laggard",
                "industry_tier": "neutral",
                "mainline_tier": "unknown",
                "market_state": "low_volume_wait",
                "leader_strength_rank": 0,
                "leader_strength_score": 0.0,
                "multi_timeframe_resonance_score": 20.0,
            }
        )

        result = score_low_buy_candidate_for_production(candidate)

        self.assertEqual(result.score_cap, 55.0)
        self.assertLessEqual(result.production_score or 0.0, 55.0)

    def test_cold_laggard_outside_weak_market_caps_score_to_68(self) -> None:
        candidate = _front_row_candidate().model_copy(
            update={
                "leader_rank": "laggard",
                "industry_tier": "cold",
                "mainline_tier": "unknown",
                "market_state": "repair",
                "leader_strength_rank": 0,
                "leader_strength_score": 0.0,
                "multi_timeframe_resonance_score": 20.0,
            }
        )

        result = score_low_buy_candidate_for_production(candidate)

        self.assertEqual(result.front_row_tier, "cold_laggard")
        self.assertEqual(result.score_cap, 68.0)
        self.assertLessEqual(result.production_score or 0.0, 68.0)
        self.assertEqual(result.decision, "watch_only")

    def test_retreat_market_caps_score_to_50(self) -> None:
        candidate = _front_row_candidate().model_copy(
            update={"market_state": "high_flyer_retreat", "multi_timeframe_resonance_score": 20.0}
        )

        result = score_low_buy_candidate_for_production(candidate)

        self.assertEqual(result.score_cap, 50.0)
        self.assertLessEqual(result.production_score or 0.0, 50.0)
        self.assertEqual(result.decision, "watch_only_retreat_market")

    def test_paused_production_strategy_has_no_production_score(self) -> None:
        candidate = _front_row_candidate("n_pattern_short_wash")

        result = score_low_buy_candidate_for_production(candidate)

        self.assertIsNone(result.production_score)
        self.assertEqual(result.decision, "paused_strategy_watch_only")
        self.assertIn("paused_production_strategy", result.exclusion_reasons)

    def test_hard_risk_excludes_candidate(self) -> None:
        candidate = _front_row_candidate().model_copy(
            update={
                "hard_risk": LowBuyHardRiskOut(
                    level="block",
                    score_penalty=99.0,
                    execution_blocked=True,
                    reasons=["流动性不足"],
                    tags=["硬风控:流动性"],
                )
            }
        )

        result = score_low_buy_candidate_for_production(candidate)

        self.assertIsNone(result.production_score)
        self.assertEqual(result.decision, "excluded")
        self.assertIn("hard_risk_execution_blocked", result.exclusion_reasons)

    def test_volume_shrink_gets_no_front_row_interaction_bonus(self) -> None:
        candidate = _front_row_candidate("volume_shrink")

        result = score_low_buy_candidate_for_production(candidate)

        self.assertNotIn("strategy_front_interaction", result.score_components)

    def test_first_board_front_row_gets_interaction_bonus(self) -> None:
        candidate = _front_row_candidate("first_board")

        result = score_low_buy_candidate_for_production(candidate)

        self.assertEqual(result.score_components["strategy_front_interaction"], 6.0)


def _front_row_candidate(strategy_key: str = "first_board"):
    return _candidate(strategy_key).model_copy(
        update={
            "buy_signal_state": "soft_buy_now",
            "leader_rank": "leader",
            "industry_tier": "core_hot",
            "mainline_tier": "core_mainline",
            "leader_strength_rank": 1,
            "leader_strength_score": 76.0,
            "market_state": "repair",
            "entry_distance_pct": 0.2,
            "execution_ready": True,
            "distribution_risk_score": 1.2,
            "multi_timeframe_resonance_score": 4.0,
        }
    )


if __name__ == "__main__":
    unittest.main()
