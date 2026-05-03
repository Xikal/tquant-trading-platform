from __future__ import annotations

import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import agent
from app.core.admin_auth import require_admin_auth
from app.core.auth import require_current_user_or_agent_token
from app.core.config import get_settings
from app.core.database import get_db
from app.models.schema_defs.agent import (
    AgentOrderRecommendationResponse,
    AgentDailyReportResponse,
    AgentHealthResponse,
    AgentSignalNotificationResponse,
    AgentSignalNotificationScanResponse,
    AgentPaperPortfolioResponse,
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

    def paper_portfolio(self, db, account_id=None, *, user_id=None):  # noqa: ANN001, ARG002
        return AgentPaperPortfolioResponse(updated_at="2026-04-29 10:30:00", account_id=account_id)

    def recommend_orders(self, db, payload, *, user_id=None):  # noqa: ANN001, ARG002
        return AgentOrderRecommendationResponse(updated_at="2026-04-29 10:30:00", account_id=payload.account_id)


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


class _NotificationServiceStub:
    def send_signal(self, db, payload, *, user_id=None):  # noqa: ANN001, ARG002
        return AgentSignalNotificationResponse(
            ok=True,
            channel=payload.channel,
            symbol=payload.symbol,
            strategy_key=payload.strategy_key,
            signal_state=payload.signal_state,
            should_notify=True,
            upgraded=False,
            notification_count=1,
            message="notification sent",
        )


class _SignalScanServiceStub:
    def scan_priority_board(self, db, *, limit=12, channel="feishu", user_id=None):  # noqa: ANN001, ARG002
        return AgentSignalNotificationScanResponse(
            channel=channel,
            scanned=limit,
            sent=1,
            suppressed=limit - 1,
            message="scan ok",
        )


def _override_db():
    yield object()


def _override_user():
    class UserStub:
        id = 1
        username = "tester"
        is_active = True

    return UserStub()


class AgentRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_context = agent.context_service
        self.original_report = agent.report_service
        self.original_factory = agent.create_agent_provider
        self.original_notification_service = agent.AgentNotificationService
        self.original_signal_scan_service = agent.AgentSignalScanService
        agent.context_service = _ContextServiceStub()
        agent.report_service = _ReportServiceStub()
        agent.create_agent_provider = lambda db=None: _ProviderStub()  # noqa: ARG005
        agent.AgentNotificationService = lambda: _NotificationServiceStub()
        agent.AgentSignalScanService = lambda: _SignalScanServiceStub()
        self.app = FastAPI()
        self.app.include_router(agent.router, prefix="/api")
        self.app.dependency_overrides[get_db] = _override_db
        self.app.dependency_overrides[require_current_user_or_agent_token] = _override_user
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        agent.context_service = self.original_context
        agent.report_service = self.original_report
        agent.create_agent_provider = self.original_factory
        agent.AgentNotificationService = self.original_notification_service
        agent.AgentSignalScanService = self.original_signal_scan_service

    def test_agent_health_route(self) -> None:
        response = self.client.get("/api/agent/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_agent_api_token_can_access_safe_routes(self) -> None:
        settings = get_settings()
        original_token = settings.agent_api_token
        self.app.dependency_overrides.pop(require_current_user_or_agent_token, None)
        settings.agent_api_token = "agent-test-token"
        try:
            response = self.client.get(
                "/api/agent/health",
                headers={"Authorization": "Bearer agent-test-token"},
            )
        finally:
            settings.agent_api_token = original_token
            self.app.dependency_overrides[require_current_user_or_agent_token] = _override_user
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

    def test_paper_portfolio_route(self) -> None:
        response = self.client.get("/api/agent/context/paper-portfolio?account_id=1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["account_id"], 1)

    def test_recommend_orders_route(self) -> None:
        response = self.client.post("/api/agent/context/recommend-orders", json={"limit": 3, "account_id": 1})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["account_id"], 1)

    def test_provider_status_route(self) -> None:
        response = self.client.get("/api/agent/provider/status")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["provider"], "none")

    def test_signal_notification_route(self) -> None:
        response = self.client.post(
            "/api/agent/notify/signal",
            json={"symbol": "510300", "strategy_key": "first_board", "signal_state": "watch"},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["ok"])
        self.assertTrue(body["should_notify"])
        self.assertEqual(body["symbol"], "510300")

    def test_signal_notification_scan_route(self) -> None:
        response = self.client.post(
            "/api/agent/notify/scan-priority-board",
            json={"limit": 3, "channel": "feishu"},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["scanned"], 3)

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
