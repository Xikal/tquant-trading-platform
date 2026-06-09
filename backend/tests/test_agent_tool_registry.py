from __future__ import annotations

import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agent_tools.policy import AgentPolicy
from app.agent_tools.audit import agent_audit_metrics, audit_raw_tool_call, sanitize_arguments
from app.agent_tools.registry import get_tool_definition, list_tool_definitions
from app.core.config import AppSettings
from app.models.base import Base
from app.models.entities import AgentAuditLog


class AgentToolRegistryTests(unittest.TestCase):
    def test_registry_lists_expected_tools(self) -> None:
        names = {tool.name for tool in list_tool_definitions()}
        self.assertGreaterEqual(len(names), 18)
        self.assertTrue(
            {
                "get_agent_health",
                "get_watchlist_context",
                "get_priority_board",
                "analyze_stock",
                "get_daily_report",
                "send_test_notification",
                "send_signal_notification",
                "scan_priority_board_notifications",
                "backtest_strategy",
                "compare_strategies",
                "get_market_sentiment",
                "get_sector_heatmap",
                "get_position_t_signal",
                "get_market_state_analysis",
                "get_sector_mainline_analysis",
                "cross_validate_strategy_context",
                "check_agent_risk",
                "get_comprehensive_analysis",
            }.issubset(names)
        )
        self.assertFalse({"get_paper_portfolio", "recommend_orders", "create_paper_order"} & names)

    def test_priority_board_definition_exists(self) -> None:
        tool = get_tool_definition("get_priority_board")
        self.assertIsNotNone(tool)
        self.assertEqual(tool.method, "GET")
        self.assertEqual(tool.path, "/api/agent/context/priority-board")
        self.assertEqual(tool.permission, "read")

    def test_notification_tool_requires_notify_permission(self) -> None:
        tool = get_tool_definition("send_test_notification")
        self.assertIsNotNone(tool)
        self.assertEqual(tool.permission, "notify")
        signal_tool = get_tool_definition("send_signal_notification")
        self.assertIsNotNone(signal_tool)
        self.assertEqual(signal_tool.permission, "notify")
        scan_tool = get_tool_definition("scan_priority_board_notifications")
        self.assertIsNotNone(scan_tool)
        self.assertEqual(scan_tool.permission, "notify")

    def test_paper_trading_tools_are_removed_from_registry(self) -> None:
        self.assertIsNone(get_tool_definition("get_paper_portfolio"))
        self.assertIsNone(get_tool_definition("recommend_orders"))
        self.assertIsNone(get_tool_definition("create_paper_order"))

    def test_capability_restriction_denies_unlisted_capability(self) -> None:
        tool = get_tool_definition("get_priority_board")
        self.assertIsNotNone(tool)
        policy = AgentPolicy(AppSettings(agent_allowed_capabilities=["health_read"]))
        error = policy.check_tool_allowed(tool)
        self.assertIsNotNone(error)
        self.assertEqual(error.code, "TOOL_PERMISSION_DENIED")

    def test_sensitive_arguments_are_masked(self) -> None:
        masked = sanitize_arguments(
            {
                "token": "abc",
                "nested": {"api_key": "secret", "symbol": "510300"},
                "items": [{"password": "x"}],
            }
        )
        self.assertEqual(masked["token"], "***")
        self.assertEqual(masked["nested"]["api_key"], "***")
        self.assertEqual(masked["nested"]["symbol"], "510300")
        self.assertEqual(masked["items"][0]["password"], "***")

    def test_audit_log_includes_agent_security_fields(self) -> None:
        with self.assertLogs("agent.audit", level="INFO") as logs:
            audit_raw_tool_call(
                trace_id="agent_test",
                provider="none",
                tool_name="get_agent_health",
                permission="read",
                arguments={"token": "secret", "symbol": "510300"},
                ok=False,
                duration_ms=12,
                error_code="TOOL_PERMISSION_DENIED",
                agent_id="agent-analyst",
                ip_address="127.0.0.1",
            )

        message = logs.output[0]
        self.assertIn("'agent_id': 'agent-analyst'", message)
        self.assertIn("'tool': 'get_agent_health'", message)
        self.assertIn("'outcome': 'denied'", message)
        self.assertIn("'latency_ms': 12", message)
        self.assertIn("'ip_address': '127.0.0.1'", message)
        self.assertIn("'token': '***'", message)

    def test_agent_audit_metrics_count_success_and_failure(self) -> None:
        engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine, future=True)
        with SessionLocal() as db:
            db.add_all(
                [
                    _audit_row("trace_1", "get_agent_health", True),
                    _audit_row("trace_2", "get_priority_board", False),
                ]
            )
            db.commit()

            metrics = agent_audit_metrics(db)

        engine.dispose()
        self.assertEqual(metrics["calls_total"], 2)
        self.assertEqual(metrics["success_total"], 1)
        self.assertEqual(metrics["failure_total"], 1)

    def test_agent_audit_metrics_return_zero_when_db_unavailable(self) -> None:
        metrics = agent_audit_metrics(object())

        self.assertEqual(metrics["calls_total"], 0)
        self.assertEqual(metrics["success_total"], 0)
        self.assertEqual(metrics["failure_total"], 0)


def _audit_row(trace_id: str, tool_name: str, ok: bool) -> AgentAuditLog:
    return AgentAuditLog(
        trace_id=trace_id,
        provider_name="none",
        tool_name=tool_name,
        permission="read",
        input_arguments="{}",
        result_summary="{}",
        ok=ok,
        duration_ms=12,
        error_code="" if ok else "TOOL_PERMISSION_DENIED",
    )


if __name__ == "__main__":
    unittest.main()
