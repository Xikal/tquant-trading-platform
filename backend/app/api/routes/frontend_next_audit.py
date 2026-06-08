from __future__ import annotations

import hashlib
import json
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.models.entities import User
from app.services.operation_audit import record_operation_audit


def frontend_next_write_headers(request: Request) -> dict[str, str]:
    keys = {
        "client_request_id": "X-Frontend-Next-Client-Request-Id",
        "contract_id": "X-Frontend-Next-Contract-Id",
        "contract_state": "X-Frontend-Next-Contract-State",
        "operation": "X-Frontend-Next-Operation",
        "source": "X-Frontend-Next-Source",
        "write_mode": "X-Frontend-Next-Write-Mode",
    }
    return {name: request.headers.get(header, "") for name, header in keys.items()}


def record_frontend_next_audit(
    db: Session,
    *,
    request: Request,
    operation: str,
    user: User | None = None,
    resource_type: str = "",
    resource_id: str | int = "",
    status: str = "ok",
    detail: dict[str, Any] | None = None,
) -> int | None:
    safe_write = frontend_next_write_headers(request)
    audit_detail = {
        "source": "frontend-next",
        "safe_write": safe_write,
        "strategy_boundaries": {
            "changed_priority_board": False,
            "changed_production_score": False,
            "changed_production_sort": False,
        },
        **(detail or {}),
    }
    return record_operation_audit(
        db,
        operation=operation,
        user=user,
        resource_type=resource_type,
        resource_id=resource_id,
        status=status,
        operator_ip=getattr(request.client, "host", "") if request.client else "",
        detail=audit_detail,
    )


def stable_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
