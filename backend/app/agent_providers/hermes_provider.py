from __future__ import annotations

from typing import Any

from app.agent_providers.base import AgentProvider, ProviderNotConfigured
from app.agent_providers.remote_gateway import RemoteAgentGatewayClient
from app.agent_tools.schemas import ToolDefinition
from app.core.config import get_settings
from app.models.schema_defs.agent import AgentProviderHealth


class HermesProvider(AgentProvider):
    """Hermes adapter seam.

    The first production-safe mode keeps tool execution inside Agent Safe API.
    Hermes can orchestrate prompts externally, but this provider never grants
    database or shell access and still uses registry + policy + audit.
    """

    name = "hermes"
    external_agent = True

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.settings = get_settings()

    def is_available(self) -> bool:
        return bool(self.settings.hermes_api_url)

    def health(self) -> AgentProviderHealth:
        warnings: list[str] = []
        if not self.settings.hermes_api_url:
            warnings.append("HERMES_API_URL 未配置，Hermes Provider 当前不可调用。")
        else:
            warnings.append("Hermes 已配置；工具调用仍通过 Agent Safe API 执行，默认不放开写入工具。")
        return AgentProviderHealth(
            provider=self.name,
            available=self.is_available(),
            external_agent=True,
            warnings=warnings,
        )

    def _invoke_allowed_tool(self, tool: ToolDefinition, arguments: dict[str, Any]) -> Any:
        if not self.settings.hermes_api_url:
            raise ProviderNotConfigured("HERMES_API_URL is not configured.")
        return RemoteAgentGatewayClient(
            base_url=self.settings.hermes_api_url,
            api_key=self.settings.hermes_api_key,
        ).invoke(tool, arguments)
