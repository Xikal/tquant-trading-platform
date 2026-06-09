from __future__ import annotations

import unittest
from unittest.mock import patch

from app.agent_providers.base import ProviderUnavailable
from app.agent_providers.custom_http_provider import CustomHttpProvider
from app.agent_providers.hermes_provider import HermesProvider
from app.agent_providers.none_provider import NoneProvider
from app.agent_providers.remote_gateway import RemoteAgentGatewayClient
from app.agent_tools.registry import get_tool_definition


class _FakeLocalInvoker:
    def __init__(self, db) -> None:  # noqa: ANN001
        self.db = db

    def invoke(self, tool, arguments):  # noqa: ANN001
        return {"tool": tool.name, "arguments": arguments}


class _RemoteErrorResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"ok": False, "error": {"message": "gateway rejected"}}


class _RemoteErrorClient:
    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args) -> None:  # noqa: ANN002
        return None

    def post(self, *args, **kwargs) -> _RemoteErrorResponse:  # noqa: ANN002, ANN003
        return _RemoteErrorResponse()


class _RemoteStatusFailureResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"status": "failed", "message": "workflow failed"}


class _RemoteStatusFailureClient(_RemoteErrorClient):
    def post(self, *args, **kwargs) -> _RemoteStatusFailureResponse:  # noqa: ANN002, ANN003
        return _RemoteStatusFailureResponse()


class AgentProviderTests(unittest.TestCase):
    def test_none_provider_reports_available(self) -> None:
        provider = NoneProvider()
        health = provider.health()
        self.assertTrue(health.available)
        self.assertFalse(health.external_agent)

    def test_notify_tool_is_denied_by_default(self) -> None:
        provider = NoneProvider()
        provider.policy.settings.agent_enable_notify_tools = False
        result = provider.invoke_tool("send_test_notification", {"channel": "feishu"})
        self.assertFalse(result.ok)
        self.assertIsNotNone(result.error)
        self.assertEqual(result.error.code, "TOOL_PERMISSION_DENIED")
        signal_result = provider.invoke_tool(
            "send_signal_notification",
            {"symbol": "510300", "signal_state": "near_entry"},
        )
        self.assertFalse(signal_result.ok)
        self.assertIsNotNone(signal_result.error)
        self.assertEqual(signal_result.error.code, "TOOL_PERMISSION_DENIED")
        scan_result = provider.invoke_tool("scan_priority_board_notifications", {"limit": 3})
        self.assertFalse(scan_result.ok)
        self.assertIsNotNone(scan_result.error)
        self.assertEqual(scan_result.error.code, "TOOL_PERMISSION_DENIED")

    def test_write_tool_is_denied_by_default(self) -> None:
        provider = NoneProvider()
        provider.policy.settings.agent_enable_write_tools = False
        result = provider.invoke_tool("run_platform_autopilot", {"auto_repair": False})
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

    def test_hermes_provider_missing_config_returns_not_configured(self) -> None:
        provider = HermesProvider()
        provider.settings.hermes_api_url = ""
        self.assertFalse(provider.health().available)
        result = provider.invoke_tool("get_priority_board", {"limit": 12})
        self.assertFalse(result.ok)
        self.assertIsNotNone(result.error)
        self.assertEqual(result.error.code, "PROVIDER_NOT_CONFIGURED")

    def test_registry_tool_definition_used_by_provider(self) -> None:
        self.assertIsNotNone(get_tool_definition("get_priority_board"))

    def test_remote_gateway_ok_false_raises_unavailable(self) -> None:
        tool = get_tool_definition("get_priority_board")
        self.assertIsNotNone(tool)
        with patch("app.agent_providers.remote_gateway.httpx.Client", _RemoteErrorClient):
            with self.assertRaises(ProviderUnavailable):
                RemoteAgentGatewayClient(base_url="http://agent.local").invoke(tool, {"limit": 12})

    def test_remote_gateway_failed_status_raises_unavailable(self) -> None:
        tool = get_tool_definition("get_priority_board")
        self.assertIsNotNone(tool)
        with patch("app.agent_providers.remote_gateway.httpx.Client", _RemoteStatusFailureClient):
            with self.assertRaises(ProviderUnavailable):
                RemoteAgentGatewayClient(base_url="http://agent.local").invoke(tool, {"limit": 12})


if __name__ == "__main__":
    unittest.main()
