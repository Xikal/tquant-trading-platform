from __future__ import annotations

import unittest
from unittest.mock import patch

from app.agent_providers.custom_http_provider import CustomHttpProvider
from app.agent_providers.none_provider import NoneProvider
from app.agent_tools.registry import get_tool_definition


class _FakeLocalInvoker:
    def __init__(self, db) -> None:  # noqa: ANN001
        self.db = db

    def invoke(self, tool, arguments):  # noqa: ANN001
        return {"tool": tool.name, "arguments": arguments}


class AgentProviderTests(unittest.TestCase):
    def test_none_provider_reports_available(self) -> None:
        provider = NoneProvider()
        health = provider.health()
        self.assertTrue(health.available)
        self.assertFalse(health.external_agent)

    def test_notify_tool_is_denied_by_default(self) -> None:
        result = NoneProvider().invoke_tool("send_test_notification", {"channel": "feishu"})
        self.assertFalse(result.ok)
        self.assertIsNotNone(result.error)
        self.assertEqual(result.error.code, "TOOL_PERMISSION_DENIED")

    def test_unknown_tool_returns_tool_not_found(self) -> None:
        result = NoneProvider().invoke_tool("missing_tool", {})
        self.assertFalse(result.ok)
        self.assertIsNotNone(result.error)
        self.assertEqual(result.error.code, "TOOL_NOT_FOUND")

    def test_none_provider_can_invoke_read_tool_locally(self) -> None:
        with patch("app.agent_providers.none_provider.LocalSafeApiInvoker", _FakeLocalInvoker):
            result = NoneProvider(db=object()).invoke_tool("get_priority_board", {"limit": 12})
        self.assertTrue(result.ok)
        self.assertEqual(result.data["tool"], "get_priority_board")
        self.assertEqual(result.data["arguments"]["limit"], 12)

    def test_custom_http_provider_missing_config_returns_not_configured(self) -> None:
        provider = CustomHttpProvider()
        provider.settings.agent_http_gateway_url = ""
        self.assertFalse(provider.health().available)
        result = provider.invoke_tool("get_priority_board", {"limit": 12})
        self.assertFalse(result.ok)
        self.assertIsNotNone(result.error)
        self.assertEqual(result.error.code, "PROVIDER_NOT_CONFIGURED")

    def test_registry_tool_definition_used_by_provider(self) -> None:
        self.assertIsNotNone(get_tool_definition("get_priority_board"))


if __name__ == "__main__":
    unittest.main()
