from __future__ import annotations

import unittest
from types import SimpleNamespace

from app.services.agent_research_service import AgentResearchService


class _ContextStub:
    def __init__(self) -> None:
        self.analysis_calls: list[str] = []

    def priority_board(self, db, limit=12):  # noqa: ANN001, ARG002
        return SimpleNamespace(
            updated_at="2026-05-04 15:00:00",
            market_state_text="市场状态：弱势修复。",
            market_state_category="repair",
            market_state_category_text="弱势修复",
            data_quality="ok",
            data_quality_text="数据完整",
            data_quality_tags=[],
            directional_bias="neutral",
            directional_bias_text="观望",
            total_candidates=2,
            immediate_count=1,
            focus_count=1,
            track_count=0,
            hot_industries=["半导体", "机器人"],
            items=[
                SimpleNamespace(
                    rank=1,
                    symbol="300001",
                    name="测试科技",
                    latest_price=12.3,
                    change_pct=2.1,
                    priority_score=86.5,
                    buy_signal_text="确定买入",
                    strategy_titles=["主线首次分歧低吸"],
                    entry_zone="12.000-12.500",
                    stop_loss=11.4,
                    suggested_position_text="建议 10%",
                    summary="主线承接良好",
                    market_state_category="repair",
                    market_state_category_text="弱势修复",
                    data_quality="ok",
                    data_quality_text="数据完整",
                    data_quality_tags=[],
                ),
                SimpleNamespace(
                    rank=2,
                    symbol="600001",
                    name="测试制造",
                    latest_price=8.6,
                    change_pct=-0.4,
                    priority_score=72.0,
                    buy_signal_text="接近买点",
                    strategy_titles=["中盘 VWAP 回踩"],
                    entry_zone="8.300-8.700",
                    stop_loss=8.0,
                    suggested_position_text="建议 6%",
                    summary="等待价格确认",
                    market_state_category="repair",
                    market_state_category_text="弱势修复",
                    data_quality="ok",
                    data_quality_text="数据完整",
                    data_quality_tags=[],
                ),
            ],
        )

    def watchlist_context(self, db):  # noqa: ANN001, ARG002
        return SimpleNamespace(
            updated_at="2026-05-04 15:00:00",
            total=1,
            actionable_count=1,
            high_risk_count=0,
            items=[
                SimpleNamespace(
                    symbol="300001",
                    name="测试科技",
                    base_position=1000,
                    available_position=500,
                    cost_basis=10.0,
                    last_price=12.3,
                    change_pct=2.1,
                    action="positive_t",
                    action_text="正T",
                    signal_score=78,
                    tradability_score=81,
                    risk_level="medium",
                    summary="正T价差满足",
                    top_reasons=["价格进入高抛区"],
                    blocking_rules=[],
                )
            ],
        )

    def analysis(self, db, payload):  # noqa: ANN001, ARG002
        self.analysis_calls.append(payload.symbol)
        return SimpleNamespace(
            symbol=payload.symbol,
            name=f"{payload.symbol}名称",
            last_price=10.0,
            change_pct=1.2,
            action="positive_t" if payload.symbol == "300001" else "hold",
            action_text="正T" if payload.symbol == "300001" else "观望",
            signal_score=82 if payload.symbol == "300001" else 55,
            tradability_score=80 if payload.symbol == "300001" else 50,
            risk_level="medium",
            entry_price=9.8,
            exit_price=10.8,
            stop_loss=9.2,
            take_profit=11.0,
            position_pct=0.1,
            expected_profit_pct=4.2,
            reasons=["技术面确认", "板块一致"],
            blocking_rules=[] if payload.symbol == "300001" else ["缺少主线确认"],
            summary="测试分析",
        )


class _MarketDataStub:
    def get_market_regime_fast(self):
        return SimpleNamespace(
            state="repair",
            label="弱势修复",
            description="市场处于弱势修复，优先强结构。",
            regime_confidence=0.72,
            state_strength=0.62,
            position_multiplier=0.95,
            limit_up_count=42,
            limit_down_count=3,
            broken_board_ratio=0.18,
            promotion_ratio=0.36,
            board_height=5,
            previous_board_height=4,
            stock_up_ratio=0.57,
            stock_median_change=0.3,
            hot_industries=["半导体", "机器人"],
            hot_turnover=1.4,
            hot_overlap_ratio=0.52,
            breadth_ready=True,
            emotion_ready=True,
            mainline_lifecycle_text="主线延续",
            transition_risk=0.1,
        )


class _FailingMarketDataStub:
    def get_market_regime_fast(self):
        raise RuntimeError("quote source unavailable")


class AgentResearchContextTests(unittest.TestCase):
    def test_market_state_analysis_returns_structured_read_only_context(self) -> None:
        service = AgentResearchService(context_service=_ContextStub(), market_data=_MarketDataStub())

        result = service.market_state_analysis(object())

        self.assertEqual(result["ok"], True)
        self.assertEqual(result["market_state"]["state"], "repair")
        self.assertEqual(result["market_state"]["confidence_pct"], 72)
        self.assertIn("limit_up_count", result["emotion"])
        self.assertIn("recommended_position_range", result["risk"])
        self.assertEqual(result["metadata"]["llm_used"], False)
        self.assertEqual(result["metadata"]["read_only"], True)

    def test_market_state_analysis_degrades_when_market_data_fails(self) -> None:
        service = AgentResearchService(context_service=_ContextStub(), market_data=_FailingMarketDataStub())

        result = service.market_state_analysis(object())

        self.assertEqual(result["ok"], False)
        self.assertEqual(result["market_state"]["state"], "degraded")
        self.assertTrue(result["errors"])
        self.assertEqual(result["metadata"]["read_only"], True)

    def test_cross_validate_marks_consensus_and_conflicts(self) -> None:
        context = _ContextStub()
        service = AgentResearchService(context_service=context, market_data=_MarketDataStub())

        result = service.cross_validate(object(), ["300001", "600001"])

        self.assertEqual(context.analysis_calls, ["300001", "600001"])
        self.assertEqual(result["summary"]["high_confidence_count"], 1)
        self.assertEqual(result["summary"]["conflict_count"], 1)
        self.assertEqual(result["items"][0]["consensus"], "high")
        self.assertEqual(result["items"][1]["consensus"], "conflict")

    def test_risk_check_flags_position_and_sector_limits_without_orders(self) -> None:
        service = AgentResearchService(context_service=_ContextStub(), market_data=_MarketDataStub())
        proposals = [
            {"symbol": "300001", "name": "测试科技", "sector": "半导体", "position_pct": 0.22},
            {"symbol": "300002", "name": "测试芯片", "sector": "半导体", "position_pct": 0.12},
        ]

        result = service.risk_check(object(), proposals)

        self.assertEqual(result["ok"], True)
        self.assertEqual(result["risk_level"], "block")
        self.assertGreaterEqual(len(result["violations"]), 2)
        self.assertEqual(result["metadata"]["read_only"], True)

    def test_comprehensive_analysis_runs_full_research_chain(self) -> None:
        service = AgentResearchService(context_service=_ContextStub(), market_data=_MarketDataStub())

        result = service.comprehensive_analysis(object(), ["300001", "600001"])

        self.assertEqual(result["ok"], True)
        self.assertIn("market_overview", result)
        self.assertIn("sector_mainline", result)
        self.assertIn("cross_validation", result)
        self.assertIn("risk_check", result)
        self.assertTrue(result["operation_checklist"])


if __name__ == "__main__":
    unittest.main()
