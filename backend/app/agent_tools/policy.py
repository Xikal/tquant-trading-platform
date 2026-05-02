from __future__ import annotations

from app.core.config import AppSettings, get_settings
from app.agent_tools.schemas import ToolDefinition
from app.models.schema_defs.agent import AgentErrorOut


class AgentPolicy:
    def __init__(self, settings: AppSettings | None = None) -> None:
        self.settings = settings or get_settings()

    def check_tool_allowed(self, tool: ToolDefinition) -> AgentErrorOut | None:
        if not tool.enabled:
            return AgentErrorOut(
                code="TOOL_PERMISSION_DENIED",
                message=f"Tool {tool.name} is disabled.",
            )
        if tool.permission == "read":
            return None
        if tool.permission == "write" and self.settings.agent_enable_write_tools:
            return None
        if tool.permission == "notify" and self.settings.agent_enable_notify_tools:
            return None
        return AgentErrorOut(
            code="TOOL_PERMISSION_DENIED",
            message=(
                f"Tool {tool.name} requires {tool.permission} permission, "
                f"but {tool.permission} tools are disabled."
            ),
            retryable=False,
        )

    def tool_enabled_for_provider(self, tool: ToolDefinition) -> bool:
        return self.check_tool_allowed(tool) is None
