from __future__ import annotations

import unittest

from app.services.low_buy.front_row_filter import (
    FrontRowFilterConfig,
    candidate_front_row_decision,
    filter_front_row_candidates,
    filter_priority_front_row_candidates,
)
from app.services.low_buy.priority_types import PriorityCandidate, StrategyHit
from scripts.low_buy_market_backtest_reporting import StrategyBacktestStats, TradeOutcome
from scripts.strategy_24m_front_row_filter import front_row_filter_ab_summary

from test_priority_weighting import _candidate


class LowBuyFrontRowFilterBacktestTests(unittest.TestCase):
    def test_front_row_filter_defaults_to_noop_until_enabled(self) -> None:
        rear = _candidate().model_copy(update={"leader_rank": "laggard", "industry_tier": "cold"})

        kept, stats = filter_front_row_candidates([rear], None)

        self.assertEqual(kept, [rear])
        self.assertEqual(stats.reason_counts, {"disabled": 1})

    def test_front_row_filter_keeps_leaders_and_rejects_rear_rank_or_retreat_state(self) -> None:
        config = FrontRowFilterConfig(enabled=True)
        leader = _candidate().model_copy(
            update={
                "leader_rank": "leader",
                "industry_tier": "core_hot",
                "mainline_tier": "core_mainline",
                "leader_strength_rank": 1,
                "leader_strength_score": 72.0,
            }
        )
        rear = _candidate().model_copy(update={"leader_rank": "laggard", "industry_tier": "cold"})
        retreat = leader.model_copy(update={"market_state": "high_flyer_retreat"})

        self.assertEqual(candidate_front_row_decision(leader, config), (True, "strong_front_row"))
        self.assertEqual(candidate_front_row_decision(rear, config), (False, "rear_rank"))
        self.assertEqual(candidate_front_row_decision(retreat, config), (False, "blocked_market_state"))

    def test_priority_front_row_filter_keeps_symbol_when_any_hit_is_front_row(self) -> None:
        config = FrontRowFilterConfig(enabled=True)
        leader_hit = _hit(
            "classic_retrace",
            _candidate().model_copy(
                update={
                    "leader_rank": "leader",
                    "industry_tier": "core_hot",
                    "leader_strength_rank": 1,
                    "leader_strength_score": 70.0,
                }
            ),
        )
        rear_hit = _hit(
            "first_board",
            _candidate("first_board").model_copy(update={"leader_rank": "laggard", "industry_tier": "cold"}),
        )
        rows = [PriorityCandidate(symbol="000001", hits=[rear_hit, leader_hit])]

        filtered, stats = filter_priority_front_row_candidates(rows, config)

        self.assertEqual([row.symbol for row in filtered], ["000001"])
        self.assertEqual([hit.strategy_key for hit in filtered[0].hits], ["classic_retrace"])
        self.assertEqual(stats.kept_count, 1)

    def test_front_row_ab_summary_reports_retention_and_shadow_only_decision(self) -> None:
        baseline = _stats(
            "classic_retrace",
            [_outcome("2026-04-20", -1.0), _outcome("2026-04-21", 2.0), _outcome("2026-04-22", 1.5)],
        )
        front_row = _stats(
            "classic_retrace",
            [_outcome("2026-04-21", 2.0), _outcome("2026-04-22", 1.5)],
            front_row_rejections={"rear_rank": 1},
        )

        summary = front_row_filter_ab_summary(
            baseline_stats={"classic_retrace": baseline},
            front_row_stats={"classic_retrace": front_row},
            config=FrontRowFilterConfig(enabled=True),
        )

        self.assertEqual(summary["delta"]["sample_retention_rate_pct"], 66.67)
        self.assertGreater(summary["delta"]["avg_trade_return_pct_delta"], 0)
        self.assertEqual(summary["front_row_only"]["front_row_rejected_count"], 1)
        self.assertIn(summary["decision"], {"research_only_insufficient_sample", "shadow_validation_candidate"})


def _hit(strategy_key: str, candidate) -> StrategyHit:
    return StrategyHit(
        strategy_key=strategy_key,
        strategy_title=strategy_key,
        family_key="test",
        candidate=candidate,
        strategy_weight_score=50.0,
        context_bonus=0.0,
    )


def _stats(
    strategy_key: str,
    outcomes: list[TradeOutcome],
    *,
    front_row_rejections: dict[str, int] | None = None,
) -> StrategyBacktestStats:
    stat = StrategyBacktestStats(
        strategy_key=strategy_key,
        strategy_title=strategy_key,
        strategy_family="test_family",
        strategy_family_text="测试策略族",
        outcomes=outcomes,
        evaluated_count=len(outcomes),
    )
    for reason, count in (front_row_rejections or {}).items():
        stat.record_front_row_filter(reason, count)
    return stat


def _outcome(signal_date: str, net_return_pct: float) -> TradeOutcome:
    return TradeOutcome(
        symbol="000001",
        name="测试",
        signal_date=signal_date,
        strategy_key="classic_retrace",
        buy_signal_state="buy_now",
        entry_price=10.0,
        execution_status="filled",
        net_return_pct=net_return_pct,
        execution_exit_reason="触发首次止盈位。",
        return_1d=net_return_pct,
        return_2d=net_return_pct,
        return_3d=net_return_pct,
        return_4d=net_return_pct,
        return_5d=net_return_pct,
        max_gain_5d=max(net_return_pct, 0.0),
        max_drawdown_5d=min(net_return_pct, 0.0),
        entry_trade_date=signal_date,
        exit_trade_date=signal_date,
    )


if __name__ == "__main__":
    unittest.main()
