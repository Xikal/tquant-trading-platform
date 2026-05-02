from __future__ import annotations

import unittest

from app.models.schemas import TradingRuleOut
from app.services.quant_engine_models import ScoreSnapshot, TradePlan
from app.services.quant_engine_output import build_suggestion


def _scores() -> ScoreSnapshot:
    return ScoreSnapshot(
        tradability_score=82.0,
        event_penalty=0.0,
        scenario="盘中确认",
        market_state="repair",
        market_state_text="修复中",
        market_bonus=0.0,
        positive_score=76.0,
        negative_score=48.0,
        signal_score=76.0,
        risk_score=28.0,
        risk_level="low",
        positive_threshold=62.0,
        negative_threshold=64.0,
    )


def _rules() -> TradingRuleOut:
    return TradingRuleOut(
        symbol="510300",
        turnaround_mode="t0",
        supports_positive_t=True,
        supports_negative_t=True,
        same_day_sell_allowed=True,
        requires_base_position=True,
        notes="ETF 可日内回转",
    )


class QuantEnginePlainDecisionTests(unittest.TestCase):
    def test_positive_t_outputs_plain_execution_text(self) -> None:
        plan = TradePlan(
            action="positive_t",
            entry_price=4.07,
            exit_price=4.13,
            stop_loss=4.03,
            take_profit=4.13,
            position_pct=25.0,
            expected_profit_pct=1.47,
            expected_loss_pct=0.98,
            risk_reward_ratio=1.5,
            slippage_bps=4.0,
            min_profit_pct=0.8,
            min_risk_reward_ratio=1.0,
        )

        suggestion = build_suggestion(
            action="positive_t",
            trade_plan=plan,
            scores=_scores(),
            reasons=["回踩承接"],
            blocking_rules=[],
            rules=_rules(),
        )

        self.assertEqual(suggestion.plain_action_text, "今天适合正T")
        self.assertIn("4.070", suggestion.plain_execution_text)
        self.assertIn("取消正T", suggestion.plain_invalid_condition)

    def test_negative_t_outputs_buyback_constraint(self) -> None:
        plan = TradePlan(
            action="negative_t",
            entry_price=4.18,
            exit_price=4.08,
            stop_loss=4.22,
            take_profit=4.08,
            position_pct=20.0,
            expected_profit_pct=2.39,
            expected_loss_pct=0.96,
            risk_reward_ratio=2.4,
            slippage_bps=4.0,
            min_profit_pct=0.8,
            min_risk_reward_ratio=1.0,
            buyback_trigger="回落至 VWAP 下方才接回。",
        )

        suggestion = build_suggestion(
            action="negative_t",
            trade_plan=plan,
            scores=_scores(),
            reasons=["冲高衰竭"],
            blocking_rules=[],
            rules=_rules(),
        )

        self.assertEqual(suggestion.plain_action_text, "今天适合反T")
        self.assertIn("接不回不追", suggestion.plain_execution_text)
        self.assertIn("回落至 VWAP", suggestion.plain_execution_text)

    def test_hold_outputs_first_hard_blocker(self) -> None:
        plan = TradePlan(
            action="hold",
            entry_price=None,
            exit_price=None,
            stop_loss=None,
            take_profit=None,
            position_pct=0.0,
            expected_profit_pct=0.0,
            expected_loss_pct=0.0,
            risk_reward_ratio=0.0,
            slippage_bps=4.0,
            min_profit_pct=0.8,
            min_risk_reward_ratio=0.0,
        )

        suggestion = build_suggestion(
            action="hold",
            trade_plan=plan,
            scores=_scores(),
            reasons=["观望"],
            blocking_rules=["价差不够，不能覆盖成本。"],
            rules=_rules(),
        )

        self.assertEqual(suggestion.plain_action_text, "今天别动")
        self.assertIn("价差不够", suggestion.plain_action_reason)
        self.assertIn("不追单", suggestion.plain_execution_text)


if __name__ == "__main__":
    unittest.main()
