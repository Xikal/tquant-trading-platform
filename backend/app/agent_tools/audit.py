from __future__ import annotations

import logging
import json
from typing import Any

from sqlalchemy.orm import Session

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
    db: Session | None = None,
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
        db=db,
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
    db: Session | None = None,
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
    _persist_audit_log(
        trace_id=trace_id,
        provider=provider,
        tool_name=tool_name,
        permission=permission,
        arguments=sanitize_arguments(arguments),
        ok=ok,
        duration_ms=duration_ms,
        error_code=error_code,
        db=db,
    )


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(marker in lowered for marker in SENSITIVE_KEYS)


def _persist_audit_log(
    *,
    trace_id: str,
    provider: str,
    tool_name: str,
    permission: str,
    arguments: Any,
    ok: bool,
    duration_ms: int,
    error_code: str | None,
    db: Session | None,
) -> None:
    if db is None or not all(hasattr(db, attr) for attr in ("add", "commit", "rollback")):
        return
    try:
        from app.models.entities import AgentAuditLog

        db.add(
            AgentAuditLog(
                trace_id=trace_id,
                provider_name=provider,
                tool_name=tool_name,
                permission=permission,
                input_arguments=json.dumps(arguments, ensure_ascii=False, default=str),
                result_summary=json.dumps(
                    {"ok": ok, "error_code": error_code or ""},
                    ensure_ascii=False,
                ),
                ok=ok,
                duration_ms=duration_ms,
                error_code=error_code or "",
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.warning("failed to persist agent audit log: trace_id=%s tool=%s", trace_id, tool_name)
