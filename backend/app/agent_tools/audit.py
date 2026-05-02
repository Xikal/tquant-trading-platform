from __future__ import annotations

import logging
from typing import Any

from app.core.config import get_settings
from app.core.timezone import beijing_now_string
from app.agent_tools.schemas import ToolDefinition

logger = logging.getLogger("agent.audit")

SENSITIVE_KEYS = (
    "token",
    "api_key",
    "apikey",
    "password",
    "passwd",
    "secret",
    "database_url",
    "authorization",
    "cookie",
    "key",
)


def sanitize_arguments(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "***" if _is_sensitive_key(key) else sanitize_arguments(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [sanitize_arguments(item) for item in value]
    return value


def audit_tool_call(
    *,
    trace_id: str,
    provider: str,
    tool: ToolDefinition,
    arguments: dict[str, Any],
    ok: bool,
    duration_ms: int,
    error_code: str | None,
) -> None:
    audit_raw_tool_call(
        trace_id=trace_id,
        provider=provider,
        tool_name=tool.name,
        permission=tool.permission,
        arguments=arguments,
        ok=ok,
        duration_ms=duration_ms,
        error_code=error_code,
    )


def audit_raw_tool_call(
    *,
    trace_id: str,
    provider: str,
    tool_name: str,
    permission: str,
    arguments: dict[str, Any],
    ok: bool,
    duration_ms: int,
    error_code: str | None,
) -> None:
    if not get_settings().agent_audit_enabled:
        return
    logger.info(
        "agent_tool_call %s",
        {
            "trace_id": trace_id,
            "provider": provider,
            "tool_name": tool_name,
            "permission": permission,
            "arguments": sanitize_arguments(arguments),
            "ok": ok,
            "duration_ms": duration_ms,
            "error_code": error_code,
            "created_at": beijing_now_string(),
        },
    )


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(marker in lowered for marker in SENSITIVE_KEYS)
