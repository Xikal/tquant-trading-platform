from __future__ import annotations

from typing import Any

from app.agent_providers.base import AgentProvider, ProviderNotConfigured
from app.agent_providers.remote_gateway import RemoteAgentGatewayClient
from app.agent_tools.schemas import ToolDefinition
from app.core.config import get_settings
from app.models.schema_defs.agent import AgentProviderHealth


class ReservedRemoteProvider(AgentProvider):
    name = "reserved"
    external_agent = True
    api_url_setting = ""
    api_key_setting = ""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.settings = get_settings()

    def is_available(self) -> bool:
        return bool(self._api_url())

    def health(self) -> AgentProviderHealth:
        warnings = []
        if not self._api_url():
            warnings.append(f"{self.api_url_setting.upper()} 未配置，{self.name} Provider 仅保留接口骨架。")
        else:
            warnings.append(f"{self.name} Provider 已配置，将按通用 HTTP Agent Gateway 协议转发工具调用。")
        return AgentProviderHealth(
            provider=self.name,
            available=self.is_available(),
            external_agent=True,
            warnings=warnings,
        )

    def _invoke_allowed_tool(self, tool: ToolDefinition, arguments: dict[str, Any]) -> Any:
        if not self._api_url():
            raise ProviderNotConfigured(f"{self.name} provider is not configured.")
        return RemoteAgentGatewayClient(
            base_url=self._api_url(),
            api_key=self._api_key(),
        ).invoke(tool, arguments)

    def _api_url(self) -> str:
        return str(getattr(self.settings, self.api_url_setting, "") or "")

    def _api_key(self) -> str:
        return str(getattr(self.settings, self.api_key_setting, "") or "")
