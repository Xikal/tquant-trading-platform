from __future__ import annotations

from datetime import datetime
from typing import Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.admin_auth import require_admin_auth
from app.core.database import get_db
from app.core.user_permissions import paper_trade_enabled
from app.models.entities import User

router = APIRouter(prefix="/admin/users")


class AdminUserOut(BaseModel):
    id: int
    username: str
    display_name: str = ""
    is_active: bool = True
    can_paper_trade: bool = True
    roles: list[str] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AdminUsersResponse(BaseModel):
    users: list[AdminUserOut]


class AdminUserUpdate(BaseModel):
    display_name: Optional[str] = Field(default=None, max_length=64)
    is_active: Optional[bool] = None
    can_paper_trade: Optional[bool] = None
    roles: Optional[Union[list[str], str]] = None


@router.get("/whitelist", response_model=AdminUsersResponse)
def list_paper_whitelist(
    _: None = Depends(require_admin_auth),
    db: Session = Depends(get_db),
) -> AdminUsersResponse:
    rows = db.execute(
        select(User).where(User.can_paper_trade.is_(True)).order_by(User.id.desc())
    ).scalars().all()
    return AdminUsersResponse(users=[_user_out(row) for row in rows])


@router.get("", response_model=AdminUsersResponse)
def list_users(
    q: str = Query(default="", max_length=64),
    limit: int = Query(default=100, ge=1, le=500),
    _: None = Depends(require_admin_auth),
    db: Session = Depends(get_db),
) -> AdminUsersResponse:
    statement = select(User).order_by(User.id.desc()).limit(limit)
    keyword = q.strip()
    if keyword:
        like_text = f"%{keyword}%"
        statement = (
            select(User)
            .where(or_(User.username.like(like_text), User.display_name.like(like_text)))
            .order_by(User.id.desc())
            .limit(limit)
        )
    rows = db.execute(statement).scalars().all()
    return AdminUsersResponse(users=[_user_out(row) for row in rows])


@router.put("/{user_id}", response_model=AdminUserOut)
def update_user(
    user_id: int,
    payload: AdminUserUpdate,
    _: None = Depends(require_admin_auth),
    db: Session = Depends(get_db),
) -> AdminUserOut:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if payload.display_name is not None:
        user.display_name = payload.display_name.strip()
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.can_paper_trade is not None:
        user.can_paper_trade = payload.can_paper_trade
    if payload.roles is not None:
        user.roles = _roles_to_text(payload.roles)
    db.commit()
    db.refresh(user)
    return _user_out(user)


def _roles_to_text(value: Union[list[str], str]) -> str:
    if isinstance(value, str):
        return ",".join(item.strip() for item in value.split(",") if item.strip())
    return ",".join(str(item).strip() for item in value if str(item).strip())


def _user_out(user: User) -> AdminUserOut:
    roles = [item.strip() for item in (user.roles or "").split(",") if item.strip()]
    return AdminUserOut(
        id=user.id,
        username=user.username,
        display_name=user.display_name or user.username,
        is_active=user.is_active,
        can_paper_trade=paper_trade_enabled(user.can_paper_trade),
        roles=roles,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )
