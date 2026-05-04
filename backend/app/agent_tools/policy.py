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
        if tool.permission == "dangerous":
            return AgentErrorOut(
                code="TOOL_PERMISSION_DENIED",
                message=f"Tool {tool.name} requires dangerous permission, which is never enabled.",
                retryable=False,
            )
        capability_error = self._capability_error(tool)
        if capability_error is not None:
            return capability_error
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

    def _capability_error(self, tool: ToolDefinition) -> AgentErrorOut | None:
        allowed = {item.strip() for item in self.settings.agent_allowed_capabilities if item.strip()}
        if not allowed:
            return None
        missing = [item for item in tool.capabilities if item not in allowed]
        if not missing:
            return None
        return AgentErrorOut(
            code="TOOL_PERMISSION_DENIED",
            message=f"Tool {tool.name} requires capability {missing[0]}, but it is not allowed.",
            retryable=False,
        )
