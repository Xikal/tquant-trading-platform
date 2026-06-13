from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


LocalDesktopStatusValue = Literal["ok", "error", "unknown"]


class LocalDesktopComponentStatus(BaseModel):
    name: str
    status: LocalDesktopStatusValue
    latency_ms: int = 0
    message: str = ""
    details: dict[str, Any] = Field(default_factory=dict)


class LocalDesktopDirectoryStatus(BaseModel):
    key: str
    path: str
    exists: bool


class LocalDesktopLaunchGuide(BaseModel):
    key: str
    label: str
    command: str
    description: str
    optional: bool = False


class LocalDesktopStatusResponse(BaseModel):
    generated_at: datetime
    app: str
    environment: str
    version: str = ""
    components: list[LocalDesktopComponentStatus] = Field(default_factory=list)
    directories: list[LocalDesktopDirectoryStatus] = Field(default_factory=list)
    launch_guides: list[LocalDesktopLaunchGuide] = Field(default_factory=list)
    safety: dict[str, bool] = Field(default_factory=dict)
