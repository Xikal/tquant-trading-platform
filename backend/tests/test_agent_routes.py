from __future__ import annotations

import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import agent
from app.core.admin_auth import require_admin_auth
from app.core.database import get_db
from app.models.schema_defs.agent import (
    AgentDailyReportResponse,
    AgentHealthResponse,
    AgentPriorityBoardResponse,
    AgentProviderHealth,
    AgentToolResult,
    AgentWatchlistContextResponse,
)


class _ContextServiceStub:
    def health(self, db):  # noqa: ANN001, ARG002
        return AgentHealthResponse(
            status="ok",
            app="维斯量化交易平台",
            checks={"database": True, "frontend_dist": True, "watchlist_signals": True, "priority_board": True},
            updated_at="2026-04-29 10:30:00",
        )

    def watchlist_context(self, db):  # noqa: ANN001, ARG002
        return AgentWatchlistContextResponse(updated_at="2026-04-29 10:30:00", total=0, items=[])

    def priority_board(self, db, limit=12):  # noqa: ANN001, ARG002
        return AgentPriorityBoardResponse(
            updated_at="2026-04-29 10:30:00",
            market_state_text="震荡修复",
            total_candidates=0,
            items=[],
        )

    def analysis(self, db, payload):  # noqa: ANN001, ARG002
        from app.models.schema_defs.agent import AgentAnalysisResponse

        return AgentAnalysisResponse(symbol=payload.symbol, name=payload.symbol, summary="测试")


class _ReportServiceStub:
    def daily_report(self, db):  # noqa: ANN001, ARG002
        return AgentDailyReportResponse(
            trade_date="2026-04-29",
            generated_at="2026-04-29 15:10:00",
            headline="今日可执行信号 0 个，全策略优先候选 0 个。",
        )


class _ProviderStub:
    name = "none"

    def health(self):
        return AgentProviderHealth(provider="none", available=True, external_agent=False)

    def invoke_tool(self, tool_name, arguments):  # noqa: ANN001
        return AgentToolResult(
            ok=True,
            provider="none",
            tool_name=tool_name,
            data={"arguments": arguments},
            trace_id="agent_test",
        )


def _override_db():
    yield object()


class AgentRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_context = agent.context_service
        self.original_report = agent.report_service
        self.original_factory = agent.create_agent_provider
        agent.context_service = _ContextServiceStub()
        agent.report_service = _ReportServiceStub()
        agent.create_agent_provider = lambda db=None: _ProviderStub()  # noqa: ARG005
        self.app = FastAPI()
        self.app.include_router(agent.router, prefix="/api")
        self.app.dependency_overrides[get_db] = _override_db
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        agent.context_service = self.original_context
        agent.report_service = self.original_report
        agent.create_agent_provider = self.original_factory

    def test_agent_health_route(self) -> None:
        response = self.client.get("/api/agent/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_watchlist_context_route(self) -> None:
        response = self.client.get("/api/agent/context/watchlist")
        self.assertEqual(response.status_code, 200)
        self.assertIn("items", response.json())

    def test_priority_board_route(self) -> None:
        response = self.client.get("/api/agent/context/priority-board?limit=12")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["market_state_text"], "震荡修复")

    def test_daily_report_route(self) -> None:
        response = self.client.get("/api/agent/reports/daily")
        self.assertEqual(response.status_code, 200)
        self.assertIn("headline", response.json())

    def test_provider_status_route(self) -> None:
        response = self.client.get("/api/agent/provider/status")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["provider"], "none")

    def test_provider_invoke_route(self) -> None:
        self.app.dependency_overrides[require_admin_auth] = lambda: None
        response = self.client.post(
            "/api/agent/provider/invoke",
            json={"tool_name": "get_priority_board", "arguments": {"limit": 12}},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])

    def test_provider_invoke_requires_admin_auth(self) -> None:
        response = self.client.post(
            "/api/agent/provider/invoke",
            json={"tool_name": "get_priority_board", "arguments": {"limit": 12}},
        )
        self.assertEqual(response.status_code, 500)


if __name__ == "__main__":
    unittest.main()
