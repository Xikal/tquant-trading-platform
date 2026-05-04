from __future__ import annotations

import unittest

from app.agent_tools.policy import AgentPolicy
from app.agent_tools.audit import sanitize_arguments
from app.agent_tools.registry import get_tool_definition, list_tool_definitions
from app.core.config import AppSettings


class AgentToolRegistryTests(unittest.TestCase):
    def test_registry_lists_expected_tools(self) -> None:
        names = {tool.name for tool in list_tool_definitions()}
        self.assertIn("get_agent_health", names)
        self.assertIn("get_watchlist_context", names)
        self.assertIn("get_priority_board", names)
        self.assertIn("analyze_stock", names)
        self.assertIn("get_daily_report", names)
        self.assertIn("get_paper_portfolio", names)
        self.assertIn("recommend_orders", names)
        self.assertIn("send_test_notification", names)
        self.assertIn("send_signal_notification", names)
        self.assertIn("scan_priority_board_notifications", names)

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

    def test_order_recommendation_tool_requires_write_permission(self) -> None:
        tool = get_tool_definition("recommend_orders")
        self.assertIsNotNone(tool)
        self.assertEqual(tool.permission, "write")

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


if __name__ == "__main__":
    unittest.main()
