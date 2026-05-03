from __future__ import annotations

from typing import Any

import httpx

from app.agent_providers.base import ProviderUnavailable
from app.agent_tools.schemas import ToolDefinition
from app.core.config import get_settings


class RemoteAgentGatewayClient:
    """Thin adapter for external HTTP Agent gateways.

    Expected endpoint:
    POST {gateway_url}/tools/invoke
    {"tool_name": "...", "arguments": {...}, "tool": {...}}
    """

    def __init__(self, *, base_url: str, api_key: str = "") -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.settings = get_settings()

    def invoke(self, tool: ToolDefinition, arguments: dict[str, Any]) -> Any:
        if not self.base_url:
            raise ProviderUnavailable("remote agent gateway url is empty")
        payload = {
            "tool_name": tool.name,
            "arguments": arguments,
            "tool": tool.model_dump(),
        }
        try:
            with httpx.Client(timeout=max(tool.timeout_seconds, self.settings.agent_timeout_seconds, 1)) as client:
                response = client.post(f"{self.base_url}/tools/invoke", json=payload, headers=self._headers())
                response.raise_for_status()
                body = response.json()
        except httpx.TimeoutException as exc:
            raise TimeoutError(f"Remote tool {tool.name} timed out.") from exc
        except httpx.HTTPError as exc:
            raise ProviderUnavailable(f"Remote gateway unavailable: {exc}") from exc
        if isinstance(body, dict) and body.get("ok") is False:
            raise ProviderUnavailable(_remote_error_message(body))
        return body.get("data", body) if isinstance(body, dict) else body

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            return {}
        return {"Authorization": f"Bearer {self.api_key}"}


def _remote_error_message(body: dict[str, Any]) -> str:
    error = body.get("error")
    if isinstance(error, dict):
        return str(error.get("message") or error.get("code") or "Remote gateway tool failed.")
    if error:
        return str(error)
    return str(body.get("message") or "Remote gateway tool failed.")
