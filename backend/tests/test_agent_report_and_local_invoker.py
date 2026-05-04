from __future__ import annotations

import unittest
from types import SimpleNamespace

from app.agent_providers.local_safe_api import LocalSafeApiInvoker
from app.agent_tools.registry import get_tool_definition
from app.models.schema_defs.agent import AgentDailyReportResponse
from app.services.agent_report_service import AgentReportService


class _WatchlistContext:
    updated_at = "2026-05-04 15:00:00"
    total = 2
    actionable_count = 1
    high_risk_count = 1
    items = [
        SimpleNamespace(
            symbol="510300",
            name="沪深300ETF",
            action="positive_t",
            action_text="正T",
            base_position=1000,
            available_position=600,
            cost_basis=3.45,
            last_price=3.56,
            risk_level="low",
            summary="回踩后重新站稳，等待价差。",
        )
    ]


class _PriorityBoard:
    market_state_text = "弱势修复"
    immediate_count = 1
    focus_count = 1
    track_count = 0
    total_candidates = 2
    hot_industries = ["半导体"]
    items = [
        SimpleNamespace(
            rank=1,
            symbol="300001",
            name="测试科技",
            strategy_titles=["首板回调"],
            suggested_position_text="建议 10%",
            priority_score=88,
            entry_zone="10.000-10.300",
            stop_loss=9.7,
            buy_signal_text="确定买入",
            summary="价格进入买点区。",
        )
    ]


class _ReportContextStub:
    def watchlist_context(self, db):  # noqa: ANN001, ARG002
        return _WatchlistContext()

    def priority_board(self, db, limit=12):  # noqa: ANN001, ARG002
        return _PriorityBoard()


class _ReportResearchStub:
    def market_state_analysis(self, db):  # noqa: ANN001, ARG002
        return {
            "market_state": {"label": "弱势修复", "confidence_pct": 72},
            "emotion": {"limit_up_count": 30, "limit_down_count": 2, "broken_board_pct": 12},
            "risk": {"recommended_position_range": {"min_pct": 10, "max_pct": 30}, "risk_level": "medium"},
        }

    def sector_mainline_analysis(self, db):  # noqa: ANN001, ARG002
        return {
            "mainlines": [
                {"rank": 1, "sector": "半导体", "continuity_score": 78, "core_symbols": [{"symbol": "300001"}]}
            ]
        }

    def risk_check(self, db, proposals):  # noqa: ANN001, ARG002
        return {"risk_level": "clear", "summary": {"total_position_pct": 10}, "violations": []}


class _InvokerContextStub:
    def health(self, db):  # noqa: ANN001, ARG002
        return SimpleNamespace(model_dump=lambda: {"status": "ok"})

    def watchlist_context(self, db):  # noqa: ANN001, ARG002
        return SimpleNamespace(model_dump=lambda: {"items": []})

    def priority_board(self, db, limit=12):  # noqa: ANN001, ARG002
        return SimpleNamespace(model_dump=lambda: {"limit": limit})


class _InvokerReportStub:
    def daily_report(self, db):  # noqa: ANN001, ARG002
        return AgentDailyReportResponse(
            trade_date="2026-05-04",
            generated_at="2026-05-04 15:10:00",
            headline="日报",
        )


class _InvokerResearchStub:
    def market_state_analysis(self, db):  # noqa: ANN001, ARG002
        return {"context": "market_state_analysis"}

    def sector_mainline_analysis(self, db):  # noqa: ANN001, ARG002
        return {"context": "sector_mainline_analysis"}

    def cross_validate(self, db, symbols):  # noqa: ANN001, ARG002
        return {"context": "strategy_cross_validation", "symbols": symbols}

    def risk_check(self, db, proposals):  # noqa: ANN001, ARG002
        return {"context": "risk_check", "proposal_count": len(proposals)}

    def comprehensive_analysis(self, db, symbols):  # noqa: ANN001, ARG002
        return {"context": "comprehensive_analysis", "symbols": symbols}


class AgentReportAndLocalInvokerTests(unittest.TestCase):
    def test_daily_report_contains_research_sections(self) -> None:
        service = AgentReportService()
        service.context = _ReportContextStub()
        service.research = _ReportResearchStub()

        report = service.daily_report(object())

        self.assertIn("TQuant 每日决策报告", report.markdown)
        self.assertIn("市场概览", report.markdown)
        self.assertIn("持仓做T信号", report.markdown)
        self.assertEqual(report.watchlist_summary["actionable_count"], 1)
        self.assertEqual(report.priority_board_summary["immediate_count"], 1)
        self.assertEqual(report.holding_t_signals[0]["symbol"], "510300")

    def test_local_safe_api_invokes_research_context_tools(self) -> None:
        invoker = LocalSafeApiInvoker(db=object())
        invoker.context = _InvokerContextStub()
        invoker.reports = _InvokerReportStub()
        invoker.research = _InvokerResearchStub()

        expected = {
            "get_market_state_analysis": {},
            "get_sector_mainline_analysis": {},
            "cross_validate_strategy_context": {"symbols": ["510300"]},
            "check_agent_risk": {"proposals": [{"symbol": "510300"}]},
            "get_comprehensive_analysis": {"symbols": ["510300"]},
            "get_daily_report": {},
        }
        for tool_name, arguments in expected.items():
            tool = get_tool_definition(tool_name)
            self.assertIsNotNone(tool)
            result = invoker.invoke(tool, arguments)
            self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
