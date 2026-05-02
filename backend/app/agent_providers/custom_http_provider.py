from __future__ import annotations

from typing import Any

from app.agent_providers.base import AgentProvider, ProviderNotConfigured
from app.agent_providers.http_safe_api import HttpSafeApiClient
from app.agent_tools.schemas import ToolDefinition
from app.core.config import get_settings
from app.models.schema_defs.agent import AgentProviderHealth


class CustomHttpProvider(AgentProvider):
    name = "custom_http"
    external_agent = True

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.settings = get_settings()

    def is_available(self) -> bool:
        return bool(self.settings.agent_http_gateway_url)

    def health(self) -> AgentProviderHealth:
        warnings = []
        if not self.settings.agent_http_gateway_url:
            warnings.append("AGENT_HTTP_GATEWAY_URL 未配置，Custom HTTP Provider 当前不可调用。")
        return AgentProviderHealth(
            provider=self.name,
            available=self.is_available(),
            external_agent=True,
            warnings=warnings,
        )

    def _invoke_allowed_tool(self, tool: ToolDefinition, arguments: dict[str, Any]) -> Any:
        if not self.settings.agent_http_gateway_url:
            raise ProviderNotConfigured("AGENT_HTTP_GATEWAY_URL is not configured.")
        # 第一阶段保持安全：仍只调用本项目 Agent Safe API；外部 Gateway 转发在此扩展。
        return HttpSafeApiClient().invoke(tool, arguments)
