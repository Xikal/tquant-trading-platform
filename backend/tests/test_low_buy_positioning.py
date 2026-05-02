from __future__ import annotations

import unittest

from app.models.schemas import (
    LowBuyCandidateOut,
    LowBuyHistorySectionOut,
    LowBuyScreenerResponse,
    LowBuyStrategyPerformanceOut,
)
from app.services.low_buy.candidate import LowBuyCandidateMixin
from app.services.low_buy.performance import LowBuyPerformanceMixin
from app.services.low_buy.shared import LOW_BUY_PERFORMANCE_SNAPSHOT_VERSION, LOW_BUY_RESULT_VERSION


class _CandidateService(LowBuyCandidateMixin):
    pass


class _PerformanceService(LowBuyPerformanceMixin, LowBuyCandidateMixin):
    def __init__(self, performance: LowBuyStrategyPerformanceOut | None) -> None:
        self.performance = performance

    def _load_strategy_performance_snapshot(self, db, strategy: str, latest_trade_date: str, lookback_days: int = 60):  # noqa: ARG002
        return self.performance

    def _build_strategy_performance_snapshot(self, db, strategy: str, latest_trade_date: str):  # noqa: ARG002
        return self.performance

    def _load_stock_profit_target_pct(self, db):  # noqa: ARG002
        return 3.0


def _candidate(**overrides) -> LowBuyCandidateOut:
    data = {
        "strategy_key": "classic_retrace",
        "strategy_title": "原始低吸法",
        "payload_version": LOW_BUY_RESULT_VERSION,
        "symbol": "000001",
        "name": "平安银行",
        "market": "SZ",
        "instrument_type": "stock",
        "sector_name": "银行",
        "latest_price": 10.0,
        "change_pct": 1.0,
        "quote_timestamp": "2026-04-25 10:00:00",
        "board_date": "2026-04-20",
        "board_count": 1,
        "retracement_days": 3,
        "score": 88.0,
        "entry_zone_low": 9.8,
        "entry_zone_high": 10.1,
        "stop_loss": 9.5,
        "take_profit": 11.0,
        "ma5": 9.9,
        "ma10": 9.7,
        "ma20": 9.4,
        "volume_burst_ratio": 2.0,
        "volume_shrink_ratio": 0.62,
        "support_distance_pct": 1.2,
        "execution_ready": True,
        "execution_note": "测试",
        "risk_tier": "note",
        "buy_signal_state": "buy_now",
        "buy_signal_text": "确定买入",
        "buy_signal_hint": "测试",
        "market_state": "repair",
        "market_state_text": "修复中",
        "market_position_multiplier": 0.9,
        "risk_position_multiplier": 0.62,
        "industry_tier": "core_hot",
        "industry_tier_text": "核心热点",
        "industry_position_multiplier": 1.08,
        "dynamic_position_multiplier": 1.04,
        "suggested_position_pct": 0.0,
        "suggested_position_text": "",
        "summary_reason": "测试",
        "reasons": ["测试"],
        "risks": ["测试"],
        "tags": ["测试"],
    }
    data.update(overrides)
    return LowBuyCandidateOut(**data)


def _payload(candidate: LowBuyCandidateOut) -> LowBuyScreenerResponse:
    return LowBuyScreenerResponse(
        as_of_date="2026-04-25 10:00:00",
        latest_trade_date="2026-04-25",
        pool_size=1,
        scanned_count=1,
        matched_count=1,
        retracement_distribution={},
        filters={},
        strategy_notes=[],
        confirmed_candidates=[candidate],
        history_sections=[
            LowBuyHistorySectionOut(
                title="历史",
                description="测试",
                candidates=[candidate],
            )
        ],
        candidates=[],
    )


class LowBuyPositioningTests(unittest.TestCase):
    def test_positioning_uses_distinct_market_risk_industry_dynamic_multipliers(self) -> None:
        service = _CandidateService()
        candidate = _candidate()

        positioned = service._apply_candidate_positioning(candidate)

        expected = round(30.0 * 0.9 * 0.62 * 1.08 * 1.04, 2)
        self.assertEqual(positioned.suggested_position_pct, expected)
        self.assertIn("环境 0.90", positioned.position_breakdown_text)
        self.assertIn("风险 0.62", positioned.position_breakdown_text)
        self.assertIn("动态 1.04", positioned.position_breakdown_text)

    def test_attach_strategy_performance_updates_regular_playbook_candidates(self) -> None:
        performance = LowBuyStrategyPerformanceOut(
            snapshot_version=LOW_BUY_PERFORMANCE_SNAPSHOT_VERSION,
            evaluated_signals=80,
            filled_signals=60,
            hit_rate=34.0,
            net_win_rate=-32.0,
            avg_return_5d=-2.6,
            avg_net_return_pct=-2.6,
            avg_max_drawdown_5d=-6.8,
        )
        service = _PerformanceService(performance)
        payload = _payload(_candidate(market_position_multiplier=1.0, risk_position_multiplier=1.0, industry_position_multiplier=1.0, dynamic_position_multiplier=1.0))

        updated = service._attach_strategy_performance(db=None, payload=payload, build_if_missing=False)

        self.assertIsNotNone(updated.performance)
        self.assertLess(updated.confirmed_candidates[0].suggested_position_pct, 30.0)
        self.assertLess(updated.confirmed_candidates[0].dynamic_position_multiplier, 1.0)
        self.assertEqual(
            updated.history_sections[0].candidates[0].suggested_position_pct,
            updated.confirmed_candidates[0].suggested_position_pct,
        )

    def test_performance_buckets_keep_full_context_and_sort_by_requested_field(self) -> None:
        service = _PerformanceService(None)
        records = [
            {"market_state": "repair", "return_3d": 1.0, "return_5d": 0.5, "hit": True},
            {"market_state": "broad_rally", "return_3d": 0.8, "return_5d": 3.2, "hit": True},
            {"market_state": "weight_support", "return_3d": 1.4, "return_5d": -0.4, "hit": False},
            {"market_state": "risk_release", "return_3d": -0.8, "return_5d": -2.1, "hit": False},
        ]

        buckets = service._build_performance_buckets(
            records,
            key="market_state",
            limit=None,
            sort_return_field="avg_return_5d",
        )

        self.assertEqual(len(buckets), 4)
        self.assertEqual(buckets[0].label, "broad_rally")
        self.assertEqual(buckets[-1].label, "risk_release")


if __name__ == "__main__":
    unittest.main()
