from __future__ import annotations

import unittest

from app.models.schemas import LowBuyCandidateOut, LowBuyPerformanceBucketOut, LowBuyStrategyPerformanceOut
from app.services.low_buy.priority_board import LowBuyPriorityBoardMixin, filter_priority_candidates_for_recommendation
from app.services.low_buy.priority_scoring import LowBuyPriorityScoringMixin
from app.services.low_buy.priority_types import PriorityBaseSnapshot, PriorityCandidate, StrategyHit
from app.services.low_buy.shared import LOW_BUY_RESULT_VERSION
from app.services.low_buy.strategy_families import resolve_strategy_family


class _ScoringService(LowBuyPriorityScoringMixin):
    pass


class _PriorityBoardService(LowBuyPriorityBoardMixin):
    def __init__(self) -> None:
        self.snapshot_requests: list[tuple[str, str, int]] = []
        self.recent_materializations: list[tuple[str, str]] = []
        self.base_materializations: list[tuple[str, str]] = []

    def _load_strategy_performance_snapshot(self, db, strategy: str, latest_trade_date: str, lookback_days: int):  # noqa: ARG002
        self.snapshot_requests.append((strategy, latest_trade_date, lookback_days))
        return None

    def _build_strategy_performance_snapshot(self, db, strategy: str, latest_trade_date: str):  # noqa: ARG002
        self.base_materializations.append((strategy, latest_trade_date))
        return _performance(evaluated_signals=30, hit_rate=55.0, avg_return_3d=2.0, avg_return_5d=3.0)

    def _ensure_recent_strategy_performance_snapshot(self, db, strategy: str, latest_trade_date: str):  # noqa: ARG002
        self.recent_materializations.append((strategy, latest_trade_date))
        return _performance(evaluated_signals=18, hit_rate=62.0, avg_return_3d=2.8, avg_return_5d=3.6)


def _candidate(strategy_key: str = "classic_retrace") -> LowBuyCandidateOut:
    return LowBuyCandidateOut(
        strategy_key=strategy_key,
        strategy_title=strategy_key,
        payload_version=LOW_BUY_RESULT_VERSION,
        symbol="000001",
        name="平安银行",
        market="SZ",
        instrument_type="stock",
        sector_name="银行",
        latest_price=10.0,
        change_pct=1.0,
        quote_timestamp="2026-04-24 10:00:00",
        board_date="2026-04-20",
        board_count=1,
        retracement_days=3,
        score=88.0,
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
        industry_tier="core_hot",
        industry_tier_text="核心热点",
        industry_position_multiplier=1.08,
        execution_ready=True,
        execution_note="测试",
        suggested_position_pct=20.0,
        suggested_position_text="测试",
        summary_reason="测试",
        buy_signal_state="buy_now",
        buy_signal_text="确定买入",
        buy_signal_hint="测试",
        reasons=["测试"],
        risks=["测试"],
        tags=["测试"],
    )


def _performance(
    *,
    evaluated_signals: int,
    hit_rate: float,
    avg_return_3d: float,
    avg_return_5d: float,
    net_win_rate: float | None = None,
    filled_signals: int | None = None,
    avg_max_gain_5d: float = 6.0,
    avg_max_drawdown_5d: float = -2.0,
    market_state_hit_rate: float = 0.0,
    industry_tier_hit_rate: float = 0.0,
) -> LowBuyStrategyPerformanceOut:
    return LowBuyStrategyPerformanceOut(
        evaluated_signals=evaluated_signals,
        filled_signals=evaluated_signals if filled_signals is None else filled_signals,
        net_win_rate=(hit_rate * 2 - 100) if net_win_rate is None else net_win_rate,
        hit_rate=hit_rate,
        avg_return_3d=avg_return_3d,
        avg_return_5d=avg_return_5d,
        avg_max_gain_5d=avg_max_gain_5d,
        avg_max_drawdown_5d=avg_max_drawdown_5d,
        market_state_attribution=[
            LowBuyPerformanceBucketOut(
                label="low_volume_wait",
                sample_count=12,
                hit_count=round(market_state_hit_rate * 0.12),
                hit_rate=market_state_hit_rate,
                avg_return_3d=avg_return_3d,
                avg_return_5d=avg_return_5d,
            )
        ]
        if market_state_hit_rate
        else [],
        industry_tier_attribution=[
            LowBuyPerformanceBucketOut(
                label="core_hot",
                sample_count=12,
                hit_count=round(industry_tier_hit_rate * 0.12),
                hit_rate=industry_tier_hit_rate,
                avg_return_3d=avg_return_3d,
                avg_return_5d=avg_return_5d,
            )
        ]
        if industry_tier_hit_rate
        else [],
    )


def _hit(strategy_key: str, weight: float, context_bonus: float = 0.0) -> StrategyHit:
    return StrategyHit(
        strategy_key=strategy_key,
        strategy_title=strategy_key,
        family_key=resolve_strategy_family(strategy_key),
        candidate=_candidate(strategy_key),
        strategy_weight_score=weight,
        context_bonus=context_bonus,
    )


class PriorityWeightingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = _ScoringService()
        self.priority_board = _PriorityBoardService()

    def test_priority_snapshot_warning_hides_internal_stale_strategy_keys(self) -> None:
        warning = self.priority_board._priority_snapshot_warning(
            PriorityBaseSnapshot(
                latest_trade_date="2026-04-28",
                latest_available_trade_date="2026-04-30",
                updated_at="2026-04-28 15:30:00",
                candidates=[],
                market_context=None,  # type: ignore[arg-type]
                stale_strategies=["first_board", "volume_shrink"],
            )
        )

        self.assertIn("2026-04-30", warning)
        self.assertIn("最近可用快照", warning)
        self.assertIn("部分策略结果仍在重建", warning)
        self.assertNotIn("过期策略", warning)
        self.assertNotIn("first_board", warning)

    def test_priority_recommendation_filter_excludes_chinext_and_star_market(self) -> None:
        rows = [
            PriorityCandidate(symbol="000001"),
            PriorityCandidate(symbol="300059"),
            PriorityCandidate(symbol="301001"),
            PriorityCandidate(symbol="688981"),
            PriorityCandidate(symbol="510300"),
            PriorityCandidate(symbol="588000"),
        ]

        filtered = filter_priority_candidates_for_recommendation(rows)

        self.assertEqual([row.symbol for row in filtered], ["000001", "510300", "588000"])

    def test_recent_performance_does_not_adjust_when_samples_too_small(self) -> None:
        base = _performance(evaluated_signals=42, hit_rate=51.0, avg_return_3d=1.6, avg_return_5d=2.4)
        recent = _performance(evaluated_signals=80, filled_signals=3, hit_rate=78.0, avg_return_3d=4.2, avg_return_5d=6.5)

        self.assertEqual(
            self.service._strategy_weight_score(base, recent),
            self.service._strategy_weight_score(base, None),
        )

    def test_recent_performance_lightly_boosts_weight_when_samples_are_enough(self) -> None:
        base = _performance(evaluated_signals=42, hit_rate=50.0, avg_return_3d=1.2, avg_return_5d=1.8)
        recent = _performance(evaluated_signals=80, filled_signals=60, hit_rate=70.0, avg_return_3d=3.8, avg_return_5d=5.2)

        self.assertGreater(
            self.service._strategy_weight_score(base, recent),
            self.service._strategy_weight_score(base, None),
        )

    def test_same_family_hits_are_discounted_in_aggregate_weight(self) -> None:
        same_family_hits = [
            _hit("classic_retrace", 58.0, 1.6),
            _hit("ma_support", 56.0, 1.4),
            _hit("volume_shrink", 50.0, 1.0),
        ]
        different_family_hits = [
            _hit("classic_retrace", 58.0, 1.6),
            _hit("first_board", 56.0, 1.4),
            _hit("divergence_consensus", 50.0, 1.0),
        ]

        self.assertLess(
            self.service._aggregate_strategy_weight(same_family_hits),
            self.service._aggregate_strategy_weight(different_family_hits),
        )

    def test_effective_family_count_uses_unique_families(self) -> None:
        hits = [
            _hit("classic_retrace", 58.0),
            _hit("ma_support", 56.0),
            _hit("limit_up_breakout_retrace", 54.0),
        ]

        self.assertEqual(self.service._effective_family_count(hits), 2)

    def test_effective_strategy_count_uses_raw_strategy_hits(self) -> None:
        hits = [
            _hit("classic_retrace", 58.0),
            _hit("ma_support", 56.0),
            _hit("limit_up_breakout_retrace", 54.0),
        ]

        self.assertEqual(self.service._effective_strategy_count(hits), 3)

    def test_display_strategy_titles_follow_unique_families(self) -> None:
        hits = [
            _hit("classic_retrace", 58.0, 1.2),
            _hit("volume_shrink", 56.0, 0.8),
            _hit("first_board", 54.0, 0.5),
        ]

        self.assertEqual(
            self.priority_board._display_strategy_titles(hits),
            ["volume_shrink", "first_board"],
        )

    def test_missing_recent_window_uses_materialized_snapshot_path(self) -> None:
        cache: dict[tuple[str, str, int], LowBuyStrategyPerformanceOut | None] = {}

        snapshot = self.priority_board._load_cached_strategy_performance(
            db=None,
            strategy_key="classic_retrace",
            latest_trade_date="2026-04-24",
            cache=cache,
            lookback_days=20,
            build_if_missing=True,
        )

        self.assertIsNotNone(snapshot)
        self.assertEqual(self.priority_board.base_materializations, [])
        self.assertEqual(self.priority_board.recent_materializations, [("classic_retrace", "2026-04-24")])
        self.assertEqual(
            self.priority_board.snapshot_requests,
            [("classic_retrace", "2026-04-24", 20)],
        )

    def test_market_and_industry_attribution_adjust_context_bonus(self) -> None:
        candidate = _candidate()
        strong_context = _performance(
            evaluated_signals=30,
            hit_rate=52.0,
            avg_return_3d=3.2,
            avg_return_5d=4.8,
            market_state_hit_rate=68.0,
            industry_tier_hit_rate=64.0,
        )
        weak_context = _performance(
            evaluated_signals=30,
            hit_rate=52.0,
            avg_return_3d=-1.8,
            avg_return_5d=-2.4,
            market_state_hit_rate=28.0,
            industry_tier_hit_rate=26.0,
        )

        self.assertGreater(
            self.service._strategy_context_bonus(candidate, strong_context, None),
            self.service._strategy_context_bonus(candidate, weak_context, None),
        )

    def test_priority_action_summary_uses_actual_position_pct(self) -> None:
        candidate = _candidate().model_copy(update={"suggested_position_pct": 8.5})

        summary = self.service._priority_action_summary(candidate)

        self.assertIn("8.5% 仓位", summary)
        self.assertNotIn("15% 仓位", summary)


if __name__ == "__main__":
    unittest.main()
