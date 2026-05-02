from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

import httpx

from app.core.config import get_settings
from app.agent_tools.schemas import ToolDefinition


class HttpSafeApiClient:
    def __init__(self) -> None:
        self.settings = get_settings()

    def invoke(self, tool: ToolDefinition, arguments: dict[str, Any]) -> dict[str, Any]:
        base = self.settings.agent_api_base.rstrip("/") + "/"
        path = tool.path.lstrip("/")
        if path.startswith("api/") and base.endswith("/api/"):
            path = path[4:]
        url = urljoin(base, path)
        headers = self._headers()
        timeout = max(tool.timeout_seconds, 1)
        try:
            with httpx.Client(timeout=timeout) as client:
                if tool.method.upper() == "GET":
                    response = client.get(url, params=arguments, headers=headers)
                else:
                    response = client.request(tool.method.upper(), url, json=arguments, headers=headers)
                response.raise_for_status()
                return response.json()
        except httpx.TimeoutException as exc:
            raise TimeoutError(f"Tool {tool.name} timed out after {timeout}s") from exc

    def _headers(self) -> dict[str, str]:
        if not self.settings.agent_api_token:
            return {}
        return {"Authorization": f"Bearer {self.settings.agent_api_token}"}
