from __future__ import annotations

from typing import Any

from app.agent_providers.base import AgentProvider, ProviderUnavailable
from app.agent_providers.local_safe_api import LocalSafeApiInvoker
from app.agent_tools.schemas import ToolDefinition
from app.models.schema_defs.agent import AgentProviderHealth


class NoneProvider(AgentProvider):
    name = "none"
    external_agent = False

    def is_available(self) -> bool:
        return True

    def health(self) -> AgentProviderHealth:
        return AgentProviderHealth(
            provider=self.name,
            available=True,
            external_agent=False,
            warnings=[],
        )

    def _invoke_allowed_tool(self, tool: ToolDefinition, arguments: dict[str, Any]) -> Any:
        if self.db is None:
            raise ProviderUnavailable("Local database session is required for none provider invocation.")
        return LocalSafeApiInvoker(self.db).invoke(tool, arguments)
