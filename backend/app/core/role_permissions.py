from __future__ import annotations

from typing import Literal

from fastapi import Depends, HTTPException, status

from app.core.auth import get_current_user
from app.core.config import get_settings
from app.core.user_permissions import paper_trade_enabled
from app.models.entities import User

PermissionName = Literal["read_only", "paper_trade", "strategy_config", "research", "optimizer", "admin"]


def user_roles(user: User) -> set[str]:
    return {item.strip().lower() for item in (getattr(user, "roles", "") or "").split(",") if item.strip()}


def is_admin_user(user: User) -> bool:
    roles = user_roles(user)
    return bool(getattr(user, "is_admin", False)) or "admin" in roles or "administrator" in roles


def require_research_access(user: User) -> None:
    ensure_permission(user, "research")


def has_permission(user: User, permission: PermissionName) -> bool:
    roles = user_roles(user)
    if permission == "read_only":
        return bool(getattr(user, "is_active", True))
    if is_admin_user(user):
        return True
    if permission == "paper_trade":
        return paper_trade_enabled(getattr(user, "can_paper_trade", False))
    if permission == "strategy_config":
        return "strategy_config" in roles
    if permission == "research":
        return bool({"backtest_research", "backtest_optimizer"} & roles)
    if permission == "optimizer":
        return "backtest_optimizer" in roles
    if permission == "admin":
        return False
    return False


def ensure_permission(user: User, permission: PermissionName) -> None:
    if not has_permission(user, permission):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_permission_message(permission),
        )
    if permission == "paper_trade":
        _ensure_paper_trade_mfa(user)


def require_permission(permission: PermissionName):
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        ensure_permission(current_user, permission)
        return current_user

    return dependency


def _ensure_paper_trade_mfa(user: User) -> None:
    if not get_settings().auth_require_mfa_for_paper_trade:
        return
    if getattr(user, "mfa_totp_enabled", False):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="模拟盘下单权限要求先开启动态验证码，请在系统配置的登录保护中启用",
    )


def _permission_message(permission: PermissionName) -> str:
    return {
        "read_only": "账号不可用",
        "paper_trade": "账号未开通模拟盘权限，请联系管理员加入白名单",
        "strategy_config": "账号未开通策略配置权限",
        "research": "账号未开通研究权限",
        "optimizer": "账号未开通参数优化权限",
        "admin": "需要管理员权限",
    }.get(permission, "权限不足")
