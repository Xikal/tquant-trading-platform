from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class OperationAuditOut(BaseModel):
    id: int
    user_id: int | None = None
    operation: str
    resource_type: str = ""
    resource_id: str = ""
    status: str = "ok"
    operator_ip: str = ""
    detail: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class OperationAuditListResponse(BaseModel):
    items: list[OperationAuditOut] = Field(default_factory=list)
    total: int = 0
    limit: int = 50
    offset: int = 0
