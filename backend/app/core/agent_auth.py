from __future__ import annotations

import contextvars
import hashlib
import secrets
from dataclasses import dataclass, field
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.auth import auth_service, bearer_scheme
from app.core.config import get_settings
from app.core.database import get_db
from app.models.entities import User
from app.services.auth_service import AuthError


@dataclass(frozen=True)
class AgentRequestContext:
    agent_id: str = ""
    scopes: tuple[str, ...] = ()
    ip_address: str = ""


_agent_context: contextvars.ContextVar[AgentRequestContext] = contextvars.ContextVar(
    "agent_request_context",
    default=AgentRequestContext(),
)


@dataclass(frozen=True)
class AgentTokenConfig:
    agent_id: str
    token: str = ""
    token_sha256: str = ""
    scopes: tuple[str, ...] = field(default_factory=tuple)
    rate_limit_per_hour: int = 100
    paper_only: bool = True


def current_agent_context() -> AgentRequestContext:
    return _agent_context.get()


def require_current_user_or_agent_token(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Optional[User]:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录",
        )

    token = credentials.credentials
    user = _try_current_user(db, token)
    if user is not None:
        _set_agent_state(request, agent_id="", scopes=(), auth_type="user")
        return user

    scoped = _match_scoped_agent_token(token)
    if scoped is not None:
        _set_agent_state(
            request,
            agent_id=scoped.agent_id,
            scopes=scoped.scopes,
            auth_type="agent",
        )
        return None

    legacy_token = get_settings().agent_api_token.strip()
    if legacy_token and secrets.compare_digest(token, legacy_token):
        _set_agent_state(
            request,
            agent_id="legacy-agent",
            scopes=("read", "write", "write_paper", "notify"),
            auth_type="agent",
        )
        return None

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="请先登录",
    )


def require_agent_tool_permission(tool_name: str, permission: str):
    def dependency(
        request: Request,
        current_user: Optional[User] = Depends(require_current_user_or_agent_token),
    ) -> Optional[User]:
        settings = get_settings()
        if permission == "dangerous":
            raise HTTPException(status_code=403, detail=f"Agent tool {tool_name} is not allowed.")
        if permission == "write" and not settings.agent_enable_write_tools:
            raise HTTPException(status_code=403, detail="Agent write tools are disabled.")
        if permission == "notify" and not settings.agent_enable_notify_tools:
            raise HTTPException(status_code=403, detail="Agent notify tools are disabled.")

        auth_type = getattr(request.state, "agent_auth_type", "user")
        if auth_type == "agent":
            scopes = set(getattr(request.state, "agent_scopes", ()))
            if not _scope_allows(permission, scopes):
                raise HTTPException(
                    status_code=403,
                    detail=f"Agent token does not include required scope for {tool_name}.",
                )
        return current_user

    return dependency


def _try_current_user(db: Session, token: str) -> Optional[User]:
    try:
        return auth_service.user_from_access_token(db, token)
    except AuthError:
        return None


def _match_scoped_agent_token(token: str) -> Optional[AgentTokenConfig]:
    token_sha256: str | None = None
    for config in _agent_token_configs():
        if config.token and secrets.compare_digest(token, config.token):
            return config
        if config.token_sha256:
            if token_sha256 is None:
                token_sha256 = hashlib.sha256(token.encode("utf-8")).hexdigest()
            if secrets.compare_digest(token_sha256, config.token_sha256):
                return config
    return None


def _agent_token_configs() -> list[AgentTokenConfig]:
    configs: list[AgentTokenConfig] = []
    for agent_id, raw_value in get_settings().agent_tokens.items():
        token, _, raw_scopes = raw_value.partition(":")
        scopes = tuple(scope.strip() for scope in raw_scopes.split(",") if scope.strip())
        credential = token.strip()
        if not credential:
            continue
        algorithm, separator, raw_hash = credential.partition("$")
        if separator and algorithm.lower() == "sha256":
            token_hash = raw_hash.strip().lower()
            if _is_sha256_hex(token_hash):
                configs.append(AgentTokenConfig(agent_id=agent_id, token_sha256=token_hash, scopes=scopes))
            continue
        configs.append(AgentTokenConfig(agent_id=agent_id, token=credential, scopes=scopes))
    return configs


def _is_sha256_hex(value: str) -> bool:
    if len(value) != 64:
        return False
    return all(char in "0123456789abcdef" for char in value)


def _set_agent_state(
    request: Request,
    *,
    agent_id: str,
    scopes: tuple[str, ...],
    auth_type: str,
) -> None:
    request.state.agent_id = agent_id
    request.state.agent_scopes = scopes
    request.state.agent_auth_type = auth_type
    ip_address = request.client.host if request.client else ""
    request.state.agent_ip_address = ip_address
    _agent_context.set(AgentRequestContext(agent_id=agent_id, scopes=scopes, ip_address=ip_address))


def _scope_allows(permission: str, scopes: set[str]) -> bool:
    if "*" in scopes or "admin" in scopes:
        return True
    if permission == "read":
        return "read" in scopes
    if permission == "write":
        return bool({"write", "write_paper"} & scopes)
    if permission == "notify":
        return "notify" in scopes
    return False
