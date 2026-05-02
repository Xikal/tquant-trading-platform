from __future__ import annotations

import logging
import secrets
from typing import Optional

from fastapi import Header, HTTPException, Request, status

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def require_admin_auth(
    request: Request,
    x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
    authorization: Optional[str] = Header(default=None),
) -> None:
    expected_token = get_settings().admin_api_token.strip()
    provided_token = _extract_token(x_admin_token=x_admin_token, authorization=authorization)
    if not expected_token:
        logger.error("ADMIN_API_TOKEN is not configured; admin endpoint rejected.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="管理接口未配置 ADMIN_API_TOKEN，已拒绝访问。",
        )

    if provided_token and secrets.compare_digest(provided_token, expected_token):
        return

    if provided_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="管理接口访问令牌无效。",
        )
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="管理接口需要有效的访问令牌。",
    )


def is_admin_token_configured() -> bool:
    return bool(get_settings().admin_api_token.strip())


def _extract_token(*, x_admin_token: Optional[str], authorization: Optional[str]) -> str:
    if x_admin_token:
        return x_admin_token.strip()
    if not authorization:
        return ""
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer":
        return ""
    return token.strip()
