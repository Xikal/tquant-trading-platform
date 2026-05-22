from __future__ import annotations

import hashlib
import json
import unittest
from os import environ

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.agent_tools.registry import list_tool_definitions
from app.api.routes import agent
from app.core.admin_auth import require_admin_auth
from app.core.agent_auth import require_current_user_or_agent_token
from app.core.config import get_settings
from app.core.database import get_db
from app.models.base import Base
from app.models.entities import AgentAuditLog
from app.models.schema_defs.agent import (
    AgentOrderRecommendationResponse,
    AgentBacktestRequest,
    AgentBacktestResponse,
    AgentCompareStrategiesResponse,
    AgentDailyReportResponse,
    AgentDailyReportPushResponse,
    AgentHealthResponse,
    AgentMarketSentimentResponse,
    AgentPaperOrderRequest,
    AgentPaperOrderResponse,
    AgentSignalNotificationResponse,
    AgentSignalNotificationScanResponse,
    AgentPaperPortfolioResponse,
    AgentPositionTSignalRequest,
    AgentPositionTSignalResponse,
    AgentPriorityBoardResponse,
    AgentProviderHealth,
    AgentSectorHeatmapResponse,
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

    def backtest_strategy(self, db, payload: AgentBacktestRequest):  # noqa: ANN001, ARG002
        return AgentBacktestResponse(
            strategy_key=payload.strategy_key,
            lookback_days=payload.lookback_days,
            summary="backtest ok",
        )

    def compare_strategies(self, db, strategy_keys, lookback_days=60):  # noqa: ANN001, ARG002
        return AgentCompareStrategiesResponse(
            strategy_keys=strategy_keys,
            lookback_days=lookback_days,
            strategy_count=len(strategy_keys),
            items=[{"strategy_key": key, "avg_net_return_pct": 0.0} for key in strategy_keys],
            summary="compare ok",
        )

    def market_sentiment(self):  # noqa: ANN001
        return AgentMarketSentimentResponse(updated_at="2026-04-29 10:30:00", state_text="震荡修复")

    def sector_heatmap(self, limit=20):  # noqa: ANN001
        return AgentSectorHeatmapResponse(updated_at="2026-04-29 10:30:00", limit=limit, sectors=[])

    def position_t_signal(self, db, payload: AgentPositionTSignalRequest):  # noqa: ANN001, ARG002
        return AgentPositionTSignalResponse(symbol=payload.symbol, action="hold", action_text="观望", summary="测试")

    def create_paper_order(self, db, payload: AgentPaperOrderRequest, *, user_id=None):  # noqa: ANN001, ARG002
        return AgentPaperOrderResponse(
            ok=True,
            account_id=payload.account_id,
            symbol=payload.symbol,
            side=payload.side,
            quantity=payload.quantity,
            price=payload.price,
            status="filled",
            summary="created",
        )


class _ReportServiceStub:
    def daily_report(self, db):  # noqa: ANN001, ARG002
        return AgentDailyReportResponse(
            trade_date="2026-04-29",
            generated_at="2026-04-29 15:10:00",
            headline="今日可执行信号 0 个，全策略优先候选 0 个。",
        )


class _ResearchServiceStub:
    def market_state_analysis(self, db):  # noqa: ANN001, ARG002
        return {"ok": True, "context": "market_state_analysis", "market_state": {"state": "repair"}}

    def sector_mainline_analysis(self, db):  # noqa: ANN001, ARG002
        return {"ok": True, "context": "sector_mainline_analysis", "mainlines": []}

    def cross_validate(self, db, symbols):  # noqa: ANN001, ARG002
        return {"ok": True, "context": "strategy_cross_validation", "items": [{"symbol": item} for item in symbols]}

    def risk_check(self, db, proposals):  # noqa: ANN001, ARG002
        return {"ok": True, "context": "risk_check", "summary": {"proposal_count": len(proposals)}}

    def comprehensive_analysis(self, db, symbols):  # noqa: ANN001, ARG002
        return {"ok": True, "context": "comprehensive_analysis", "symbols": symbols}


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


class _DailyWorkflowServiceStub:
    def push_daily_report(self, db, *, channel="feishu"):  # noqa: ANN001, ARG002
        return AgentDailyReportPushResponse(
            ok=True,
            channel=channel,
            trade_date="2026-05-04",
            generated_at="2026-05-04 15:10:00",
            sent=True,
            should_notify=True,
            duplicate=False,
            notification_count=1,
            message="notification sent",
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
        self.original_research = agent.research_service
        self.original_factory = agent.create_agent_provider
        self.original_notification_service = agent.AgentNotificationService
        self.original_signal_scan_service = agent.AgentSignalScanService
        self.original_daily_workflow_service = agent.AgentDailyWorkflowService
        self.original_notify_enabled = environ.get("AGENT_ENABLE_NOTIFY_TOOLS")
        self.original_write_enabled = environ.get("AGENT_ENABLE_WRITE_TOOLS")
        environ["AGENT_ENABLE_NOTIFY_TOOLS"] = "false"
        environ["AGENT_ENABLE_WRITE_TOOLS"] = "false"
        get_settings.cache_clear()
        agent.context_service = _ContextServiceStub()
        agent.report_service = _ReportServiceStub()
        agent.research_service = _ResearchServiceStub()
        agent.create_agent_provider = lambda db=None: _ProviderStub()  # noqa: ARG005
        agent.AgentNotificationService = lambda: _NotificationServiceStub()
        agent.AgentSignalScanService = lambda: _SignalScanServiceStub()
        agent.AgentDailyWorkflowService = lambda: _DailyWorkflowServiceStub()
        self.app = FastAPI()
        self.app.include_router(agent.router, prefix="/api")
        self.app.dependency_overrides[get_db] = _override_db
        self.app.dependency_overrides[require_current_user_or_agent_token] = _override_user
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        agent.context_service = self.original_context
        agent.report_service = self.original_report
        agent.research_service = self.original_research
        agent.create_agent_provider = self.original_factory
        agent.AgentNotificationService = self.original_notification_service
        agent.AgentSignalScanService = self.original_signal_scan_service
        agent.AgentDailyWorkflowService = self.original_daily_workflow_service
        environ.pop("AGENT_TOKENS", None)
        if self.original_notify_enabled is None:
            environ.pop("AGENT_ENABLE_NOTIFY_TOOLS", None)
        else:
            environ["AGENT_ENABLE_NOTIFY_TOOLS"] = self.original_notify_enabled
        if self.original_write_enabled is None:
            environ.pop("AGENT_ENABLE_WRITE_TOOLS", None)
        else:
            environ["AGENT_ENABLE_WRITE_TOOLS"] = self.original_write_enabled
        get_settings.cache_clear()

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

    def test_scoped_agent_token_can_access_read_routes(self) -> None:
        self.app.dependency_overrides.pop(require_current_user_or_agent_token, None)
        environ["AGENT_TOKENS"] = '{"agent-analyst":"scoped-read-token:read"}'
        get_settings.cache_clear()
        try:
            response = self.client.get(
                "/api/agent/health",
                headers={"Authorization": "Bearer scoped-read-token"},
            )
        finally:
            self.app.dependency_overrides[require_current_user_or_agent_token] = _override_user
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_hashed_scoped_agent_token_can_access_read_routes(self) -> None:
        self.app.dependency_overrides.pop(require_current_user_or_agent_token, None)
        token = "scoped-read-token"
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        environ["AGENT_TOKENS"] = f'{{"agent-analyst":"sha256${digest}:read"}}'
        get_settings.cache_clear()
        try:
            response = self.client.get(
                "/api/agent/health",
                headers={"Authorization": f"Bearer {token}"},
            )
        finally:
            self.app.dependency_overrides[require_current_user_or_agent_token] = _override_user
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_scoped_agent_token_without_read_scope_is_denied_for_read_route(self) -> None:
        self.app.dependency_overrides.pop(require_current_user_or_agent_token, None)
        environ["AGENT_TOKENS"] = '{"agent-analyst":"scoped-write-token:write_paper"}'
        get_settings.cache_clear()
        try:
            response = self.client.get(
                "/api/agent/health",
                headers={"Authorization": "Bearer scoped-write-token"},
            )
        finally:
            self.app.dependency_overrides[require_current_user_or_agent_token] = _override_user
        self.assertEqual(response.status_code, 403)

    def test_scoped_agent_token_without_write_scope_is_denied_for_paper_order(self) -> None:
        self.app.dependency_overrides.pop(require_current_user_or_agent_token, None)
        environ["AGENT_TOKENS"] = '{"agent-analyst":"scoped-read-token:read"}'
        get_settings.cache_clear()
        try:
            response = self.client.post(
                "/api/agent/paper/order",
                headers={"Authorization": "Bearer scoped-read-token"},
                json={"symbol": "510300", "side": "buy", "quantity": 100, "price": 4.0},
            )
        finally:
            self.app.dependency_overrides[require_current_user_or_agent_token] = _override_user
        self.assertEqual(response.status_code, 403)

    def test_scoped_agent_token_cannot_directly_create_paper_order_even_with_write_scope(self) -> None:
        self.app.dependency_overrides.pop(require_current_user_or_agent_token, None)
        environ["AGENT_ENABLE_WRITE_TOOLS"] = "true"
        environ["AGENT_TOKENS"] = '{"agent-analyst":"scoped-write-token:write_paper"}'
        get_settings.cache_clear()
        try:
            response = self.client.post(
                "/api/agent/paper/order",
                headers={"Authorization": "Bearer scoped-write-token"},
                json={"symbol": "510300", "side": "buy", "quantity": 100, "price": 4.0},
            )
        finally:
            self.app.dependency_overrides[require_current_user_or_agent_token] = _override_user
        self.assertEqual(response.status_code, 403)
        self.assertIn("用户会话", response.json()["detail"])

    def test_agent_paper_order_allows_whitelisted_user_without_mfa_when_write_tools_enabled(self) -> None:
        class UserWithoutMfa:
            id = 1
            username = "paper_agent_user"
            is_active = True
            can_paper_trade = True
            mfa_totp_enabled = False
            roles = ""

        environ["AGENT_ENABLE_WRITE_TOOLS"] = "true"
        get_settings.cache_clear()
        self.app.dependency_overrides[require_current_user_or_agent_token] = lambda: UserWithoutMfa()
        response = self.client.post(
            "/api/agent/paper/order",
            json={"symbol": "510300", "side": "buy", "quantity": 100, "price": 4.0},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])

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

    def test_daily_report_push_route_is_admin_only(self) -> None:
        response = self.client.post("/api/agent/reports/daily/push", json={"channel": "feishu"})
        self.assertEqual(response.status_code, 503)

        self.app.dependency_overrides[require_admin_auth] = lambda: None
        response = self.client.post("/api/agent/reports/daily/push", json={"channel": "feishu"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["sent"])
        self.assertEqual(response.json()["trade_date"], "2026-05-04")

    def test_paper_portfolio_route(self) -> None:
        response = self.client.get("/api/agent/context/paper-portfolio?account_id=1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["account_id"], 1)

    def test_recommend_orders_route(self) -> None:
        response = self.client.post("/api/agent/context/recommend-orders", json={"limit": 3, "account_id": 1})
        self.assertEqual(response.status_code, 403)

    def test_new_read_routes_are_available(self) -> None:
        backtest = self.client.post(
            "/api/agent/context/backtest",
            json={"strategy_key": "first_board", "lookback_days": 60},
        )
        self.assertEqual(backtest.status_code, 200)
        self.assertEqual(backtest.json()["strategy_key"], "first_board")

        compare = self.client.post(
            "/api/agent/context/compare-strategies",
            json={"strategy_keys": ["first_board", "volume_shrink"], "lookback_days": 60},
        )
        self.assertEqual(compare.status_code, 200)
        self.assertEqual(compare.json()["strategy_count"], 2)

        sentiment = self.client.get("/api/agent/context/market-sentiment")
        self.assertEqual(sentiment.status_code, 200)
        self.assertIn("state_text", sentiment.json())

        heatmap = self.client.get("/api/agent/context/sector-heatmap?limit=10")
        self.assertEqual(heatmap.status_code, 200)
        self.assertEqual(heatmap.json()["limit"], 10)

        signal = self.client.post(
            "/api/agent/context/position-t-signal",
            json={"symbol": "510300", "shares": 1000, "cost_basis": 4.0},
        )
        self.assertEqual(signal.status_code, 200)
        self.assertEqual(signal.json()["symbol"], "510300")

    def test_research_context_routes_are_available(self) -> None:
        market = self.client.get("/api/agent/context/market-state-analysis")
        self.assertEqual(market.status_code, 200)
        self.assertEqual(market.json()["context"], "market_state_analysis")

        sector = self.client.get("/api/agent/context/sector-mainline-analysis")
        self.assertEqual(sector.status_code, 200)
        self.assertEqual(sector.json()["context"], "sector_mainline_analysis")

        cross = self.client.post(
            "/api/agent/context/strategy-cross-validation",
            json={"symbols": ["510300", "300059"]},
        )
        self.assertEqual(cross.status_code, 200)
        self.assertEqual(len(cross.json()["items"]), 2)

        risk = self.client.post(
            "/api/agent/context/risk-check",
            json={"proposals": [{"symbol": "510300", "position_pct": 10}]},
        )
        self.assertEqual(risk.status_code, 200)
        self.assertEqual(risk.json()["summary"]["proposal_count"], 1)

        comprehensive = self.client.post(
            "/api/agent/context/comprehensive-analysis",
            json={"symbols": ["510300"]},
        )
        self.assertEqual(comprehensive.status_code, 200)
        self.assertEqual(comprehensive.json()["context"], "comprehensive_analysis")

    def test_provider_status_route(self) -> None:
        response = self.client.get("/api/agent/provider/status")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["provider"], "none")
        self.assertEqual(response.json()["tool_count"], len(list_tool_definitions()))
        self.assertIn("create_paper_order", response.json()["disabled_tools"])

    def test_signal_notification_route(self) -> None:
        response = self.client.post(
            "/api/agent/notify/signal",
            json={"symbol": "510300", "strategy_key": "first_board", "signal_state": "watch"},
        )
        self.assertEqual(response.status_code, 403)

    def test_signal_notification_scan_route(self) -> None:
        response = self.client.post(
            "/api/agent/notify/scan-priority-board",
            json={"limit": 3, "channel": "feishu"},
        )
        self.assertEqual(response.status_code, 403)

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
        self.assertEqual(response.status_code, 503)

    def test_audit_summary_route_returns_aggregate_without_params(self) -> None:
        engine = create_engine(
            "sqlite+pysqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            future=True,
        )
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine, future=True)
        db = SessionLocal()
        db.add_all(
            [
                _audit_row("trace_1", "agent-analyst", "get_agent_health", True),
                _audit_row("trace_2", "agent-analyst", "get_priority_board", False),
                _audit_row("trace_3", "agent-research", "get_agent_health", True),
            ]
        )
        db.commit()

        def override_audit_db():
            yield db

        self.app.dependency_overrides[get_db] = override_audit_db
        self.app.dependency_overrides[require_admin_auth] = lambda: None
        try:
            response = self.client.get("/api/agent/audit/summary?agent_id=agent-analyst")
        finally:
            db.close()
            engine.dispose()
            self.app.dependency_overrides[get_db] = _override_db
            self.app.dependency_overrides.pop(require_admin_auth, None)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["db_available"])
        self.assertEqual(payload["recent_call_count"], 2)
        self.assertEqual(payload["success_count"], 1)
        self.assertEqual(payload["failure_count"], 1)
        self.assertEqual(
            {item["tool_name"] for item in payload["tool_top"]},
            {"get_agent_health", "get_priority_board"},
        )
        self.assertNotIn("params_snapshot", payload)


def _audit_row(trace_id: str, agent_id: str, tool_name: str, ok: bool) -> AgentAuditLog:
    return AgentAuditLog(
        trace_id=trace_id,
        provider_name="none",
        tool_name=tool_name,
        permission="read",
        input_arguments=json.dumps({"token": "secret"}, ensure_ascii=False),
        result_summary=json.dumps(
            {
                "ok": ok,
                "outcome": "success" if ok else "error",
                "error_code": "" if ok else "TOOL_PERMISSION_DENIED",
                "agent_id": agent_id,
                "ip_address": "127.0.0.1",
                "summary": "ok" if ok else "denied",
            },
            ensure_ascii=False,
        ),
        ok=ok,
        duration_ms=12,
        error_code="" if ok else "TOOL_PERMISSION_DENIED",
    )


if __name__ == "__main__":
    unittest.main()
