from __future__ import annotations

from typing import Any

from app.agent_providers.base import AgentProvider, ProviderNotConfigured
from app.agent_providers.http_safe_api import HttpSafeApiClient
from app.agent_tools.schemas import ToolDefinition
from app.core.config import get_settings
from app.models.schema_defs.agent import AgentProviderHealth


class MCPProvider(AgentProvider):
    name = "mcp"
    external_agent = True

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.settings = get_settings()

    def is_available(self) -> bool:
        return bool(self.settings.agent_mcp_server_url)

    def health(self) -> AgentProviderHealth:
        warnings = []
        if not self.settings.agent_mcp_server_url:
            warnings.append("AGENT_MCP_SERVER_URL 未配置，MCP Provider 当前不可调用。")
        return AgentProviderHealth(
            provider=self.name,
            available=self.is_available(),
            external_agent=True,
            warnings=warnings,
        )

    def _invoke_allowed_tool(self, tool: ToolDefinition, arguments: dict[str, Any]) -> Any:
        if not self.settings.agent_mcp_server_url:
            raise ProviderNotConfigured("AGENT_MCP_SERVER_URL is not configured.")
        return HttpSafeApiClient().invoke(tool, arguments)
