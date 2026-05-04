from __future__ import annotations

import logging
import json
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.core.agent_auth import current_agent_context
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
    result_summary: str = "",
    db: Session | None = None,
) -> None:
    context = current_agent_context()
    audit_raw_tool_call(
        trace_id=trace_id,
        provider=provider,
        tool_name=tool.name,
        permission=tool.permission,
        arguments=arguments,
        ok=ok,
        duration_ms=duration_ms,
        error_code=error_code,
        agent_id=context.agent_id,
        ip_address=context.ip_address,
        result_summary=result_summary,
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
    agent_id: str = "",
    ip_address: str = "",
    result_summary: str = "",
    db: Session | None = None,
) -> None:
    if not get_settings().agent_audit_enabled:
        return
    outcome = "success" if ok else ("denied" if error_code == "TOOL_PERMISSION_DENIED" else "error")
    sanitized = sanitize_arguments(arguments)
    summary = (result_summary or json.dumps({"ok": ok, "error_code": error_code or ""}, ensure_ascii=False))[:200]
    logger.info(
        "agent_tool_call %s",
        {
            "trace_id": trace_id,
            "agent_id": agent_id,
            "provider": provider,
            "tool": tool_name,
            "tool_name": tool_name,
            "permission": permission,
            "params_snapshot": sanitized,
            "ok": ok,
            "outcome": outcome,
            "latency_ms": duration_ms,
            "duration_ms": duration_ms,
            "ip_address": ip_address,
            "error_code": error_code,
            "result_summary": summary,
            "created_at": beijing_now_string(),
        },
    )
    _persist_audit_log(
        trace_id=trace_id,
        provider=provider,
        tool_name=tool_name,
        permission=permission,
        arguments=sanitized,
        ok=ok,
        duration_ms=duration_ms,
        error_code=error_code,
        agent_id=agent_id,
        ip_address=ip_address,
        outcome=outcome,
        result_summary=summary,
        db=db,
    )


def agent_audit_metrics(db: Session | None) -> dict[str, int]:
    empty = {"calls_total": 0, "success_total": 0, "failure_total": 0}
    if db is None or not hasattr(db, "execute"):
        return empty
    try:
        from app.models.entities import AgentAuditLog

        total = int(db.execute(select(func.count(AgentAuditLog.id))).scalar() or 0)
        success = int(
            db.execute(select(func.count(AgentAuditLog.id)).where(AgentAuditLog.ok.is_(True))).scalar() or 0
        )
        return {
            "calls_total": total,
            "success_total": success,
            "failure_total": max(total - success, 0),
        }
    except Exception:
        _safe_rollback(db)
        logger.warning("failed to collect agent audit metrics")
        return empty


def agent_audit_summary(
    db: Session | None,
    *,
    agent_id: str | None = None,
    recent_limit: int = 100,
    top_limit: int = 10,
) -> dict[str, Any]:
    summary = {
        "db_available": False,
        "recent_limit": recent_limit,
        "recent_call_count": 0,
        "success_count": 0,
        "failure_count": 0,
        "tool_top": [],
    }
    if db is None or not hasattr(db, "execute"):
        return summary
    try:
        from app.models.entities import AgentAuditLog

        rows = (
            db.execute(
                select(AgentAuditLog)
                .order_by(AgentAuditLog.id.desc())
                .limit(max(recent_limit, 1))
            )
            .scalars()
            .all()
        )
    except Exception:
        _safe_rollback(db)
        logger.warning("failed to collect agent audit summary")
        return summary

    filtered_rows = [row for row in rows if not agent_id or _audit_agent_id(row) == agent_id]
    tool_counts: dict[str, dict[str, int | str]] = {}
    success_count = 0
    failure_count = 0
    for row in filtered_rows:
        if row.ok:
            success_count += 1
        else:
            failure_count += 1
        tool_name = str(row.tool_name or "unknown")
        item = tool_counts.setdefault(
            tool_name,
            {"tool_name": tool_name, "call_count": 0, "success_count": 0, "failure_count": 0},
        )
        item["call_count"] = int(item["call_count"]) + 1
        if row.ok:
            item["success_count"] = int(item["success_count"]) + 1
        else:
            item["failure_count"] = int(item["failure_count"]) + 1

    tool_top = sorted(
        tool_counts.values(),
        key=lambda item: (int(item["call_count"]), str(item["tool_name"])),
        reverse=True,
    )[: max(top_limit, 1)]
    return {
        "db_available": True,
        "recent_limit": recent_limit,
        "recent_call_count": len(filtered_rows),
        "success_count": success_count,
        "failure_count": failure_count,
        "tool_top": tool_top,
    }


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(marker in lowered for marker in SENSITIVE_KEYS)


def _audit_agent_id(row: Any) -> str:
    result = _json_dict(getattr(row, "result_summary", ""))
    return str(result.get("agent_id") or "")


def _json_dict(raw_value: str) -> dict[str, Any]:
    try:
        value = json.loads(raw_value or "{}")
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _safe_rollback(db: Session) -> None:
    rollback = getattr(db, "rollback", None)
    if callable(rollback):
        try:
            rollback()
        except Exception:
            return


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
    agent_id: str,
    ip_address: str,
    outcome: str,
    result_summary: str,
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
                    {
                        "ok": ok,
                        "outcome": outcome,
                        "error_code": error_code or "",
                        "agent_id": agent_id,
                        "ip_address": ip_address,
                        "summary": result_summary,
                    },
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
