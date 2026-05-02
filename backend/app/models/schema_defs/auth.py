from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AuthUserOut(BaseModel):
    id: int
    username: str
    display_name: str = ""
    can_paper_trade: bool = True
    roles: list[str] = Field(default_factory=list)
    created_at: datetime


class AuthRegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=128)
    display_name: str = Field(default="", max_length=64)
    device_name: str = Field(default="", max_length=80)


class AuthLoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=1, max_length=128)
    device_name: str = Field(default="", max_length=80)


class AuthRefreshRequest(BaseModel):
    refresh_token: str = Field(default="", max_length=300)


class AuthLogoutRequest(BaseModel):
    refresh_token: str = Field(default="", max_length=300)


class AuthTokenResponse(BaseModel):
    access_token: str
    refresh_token: str = ""
    token_type: str = "bearer"
    expires_in: int
    user: AuthUserOut


class AuthMeResponse(BaseModel):
    user: AuthUserOut


class PaperAccessResponse(BaseModel):
    can_paper_trade: bool
    reason: str = ""
