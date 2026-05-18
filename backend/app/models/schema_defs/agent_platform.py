from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class AgentPlatformAutopilotAction(BaseModel):
    action_key: str
    status: Literal["executed", "queued", "skipped", "failed"] = "skipped"
    message: str = ""
    task_id: Optional[int] = None
    detail: dict[str, Any] = Field(default_factory=dict)


class AgentPlatformAutopilotIssue(BaseModel):
    code: str
    severity: Literal["info", "warning", "error"] = "info"
    message: str
    detail: dict[str, Any] = Field(default_factory=dict)


class AgentPlatformAutopilotRunRequest(BaseModel):
    auto_repair: bool = True
    notify: bool = True
    trigger: str = "manual"


class AgentPlatformAutopilotResponse(BaseModel):
    ok: bool = True
    status: Literal["ok", "degraded", "failed"] = "ok"
    updated_at: str = ""
    trigger: str = "manual"
    auto_repair: bool = True
    issues: list[AgentPlatformAutopilotIssue] = Field(default_factory=list)
    actions: list[AgentPlatformAutopilotAction] = Field(default_factory=list)
    summary: str = ""
