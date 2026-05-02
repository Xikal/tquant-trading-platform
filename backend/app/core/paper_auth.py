from __future__ import annotations

from fastapi import Depends, HTTPException, status

from app.core.auth import get_current_user
from app.core.user_permissions import paper_trade_enabled
from app.models.entities import User


def require_paper_trading(current_user: User = Depends(get_current_user)) -> User:
    """Require the authenticated user to be in the paper-trading whitelist."""

    if not paper_trade_enabled(current_user.can_paper_trade):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号未开通模拟盘权限，请联系管理员加入白名单",
        )
    return current_user
