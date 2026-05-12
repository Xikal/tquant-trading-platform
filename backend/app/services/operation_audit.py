from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.entities import OperationAuditLog, User

logger = logging.getLogger(__name__)
_SENSITIVE_KEYS = {"token", "secret", "password", "cookie", "authorization", "api_key", "apikey"}


def record_operation_audit(
    db: Session,
    *,
    operation: str,
    user: User | None = None,
    resource_type: str = "",
    resource_id: str | int = "",
    status: str = "ok",
    operator_ip: str = "",
    detail: dict[str, Any] | None = None,
) -> None:
    try:
        db.add(
            OperationAuditLog(
                user_id=getattr(user, "id", None),
                operation=operation[:80],
                resource_type=resource_type[:80],
                resource_id=str(resource_id)[:80],
                status=status[:24],
                operator_ip=operator_ip[:80],
                detail_json=json.dumps(_redact(detail or {}), ensure_ascii=False, default=str),
            )
        )
    except Exception:
        logger.warning("failed to append operation audit log for operation=%s", operation)


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): "***" if any(item in str(key).lower() for item in _SENSITIVE_KEYS) else _redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value
