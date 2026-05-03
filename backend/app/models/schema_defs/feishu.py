from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class FeishuEventResponse(BaseModel):
    ok: bool = True
    challenge: str = ""
    message: str = ""
    response: dict[str, Any] = Field(default_factory=dict)


class FeishuBindingRequest(BaseModel):
    user_id: int
    open_id: str = Field(min_length=1, max_length=80)
    union_id: str = ""
    tenant_key: str = ""


class FeishuBindingResponse(BaseModel):
    id: int
    user_id: int
    open_id: str
    tenant_key: str = ""
    status: str = "active"
