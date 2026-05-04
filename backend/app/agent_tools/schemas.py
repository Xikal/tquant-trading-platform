from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.models.schema_defs.agent import AgentToolPermission


class ToolDefinition(BaseModel):
    name: str
    description: str
    method: str
    path: str
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    permission: AgentToolPermission = "read"
    capabilities: tuple[str, ...] = ()
    enabled: bool = True
    timeout_seconds: int = 10
