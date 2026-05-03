from __future__ import annotations

import unittest

from app.models.schema_defs.research import StrategyValidationItem
from app.services.paper.validation import _policy_recommendations


class StrategyValidationPolicyTests(unittest.TestCase):
    def test_recommendations_keep_only_stable_positive_samples(self) -> None:
        stable = StrategyValidationItem(
            strategy_key="first_board",
            filled_signals=50,
            avg_return_pct=0.8,
            net_win_rate_pct=12.0,
            profit_factor=1.6,
            walk_forward_pass_rate_pct=80.0,
        )
        weak = StrategyValidationItem(
            strategy_key="volume_shrink",
            filled_signals=60,
            avg_return_pct=-0.1,
            net_win_rate_pct=-3.0,
            profit_factor=0.9,
            walk_forward_pass_rate_pct=40.0,
        )
        sparse = StrategyValidationItem(
            strategy_key="late_session_strong_support",
            filled_signals=5,
            avg_return_pct=1.2,
            net_win_rate_pct=20.0,
        )

        recommendations = _policy_recommendations([stable, weak, sparse])

        self.assertEqual(recommendations["first_board"], "keep_production")
        self.assertEqual(recommendations["volume_shrink"], "downgrade_review_required")
        self.assertEqual(recommendations["late_session_strong_support"], "observe_insufficient_sample")


if __name__ == "__main__":
    unittest.main()
