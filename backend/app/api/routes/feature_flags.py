from __future__ import annotations

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.entities import User
from app.services.shared.feature_flags import flag_to_dict, list_feature_flags, update_feature_flag


router = APIRouter(prefix="/settings/feature-flags", dependencies=[Depends(get_current_user)])


class FeatureFlagUpdateRequest(BaseModel):
    key: str = Field(default="", max_length=64)
    enabled: bool


@router.get("")
def get_feature_flags(db: Session = Depends(get_db)) -> dict:
    return {"items": [flag_to_dict(item) for item in list_feature_flags(db)]}


@router.put("/{key}")
def put_feature_flag(
    key: str,
    payload: FeatureFlagUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _require_admin(current_user)
    try:
        payload_key = payload.key or key
        if payload_key != key:
            raise ValueError("路径 key 与请求体 key 不一致")
        flag = update_feature_flag(db, key=key, enabled=payload.enabled, current_user=current_user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"ok": True, "item": flag_to_dict(flag)}


def _require_admin(user: User) -> None:
    roles = {item.strip().lower() for item in (getattr(user, "roles", "") or "").split(",")}
    if "admin" in roles or "administrator" in roles:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
