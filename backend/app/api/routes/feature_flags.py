from __future__ import annotations

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Request, Query, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.entities import User
from app.services.shared.feature_flags import (
    flag_to_dict,
    list_feature_flag_audit,
    list_feature_flags,
    update_feature_flag,
)


router = APIRouter(prefix="/settings/feature-flags", dependencies=[Depends(get_current_user)])


class FeatureFlagUpdateRequest(BaseModel):
    key: str = Field(default="", max_length=64)
    enabled: bool


@router.get("")
def get_feature_flags(db: Session = Depends(get_db)) -> dict:
    items = [flag_to_dict(item) for item in list_feature_flags(db)]
    return {
        "items": items,
        "flags": {item["key"]: item for item in items},
        "updated_at": max((str(item.get("updated_at") or "") for item in items), default=""),
    }


@router.get("/audit")
def get_feature_flag_audit(
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _require_admin(current_user)
    return {"items": list_feature_flag_audit(db, limit=limit)}


@router.put("/{key}")
def put_feature_flag(
    key: str,
    payload: FeatureFlagUpdateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _require_admin(current_user)
    try:
        payload_key = payload.key or key
        if payload_key != key:
            raise ValueError("路径 key 与请求体 key 不一致")
        flag = update_feature_flag(
            db,
            key=key,
            enabled=payload.enabled,
            current_user=current_user,
            operator_ip=_client_ip(request),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    item = flag_to_dict(flag)
    return {"ok": True, "item": item, "flag": item}


def _require_admin(user: User) -> None:
    roles = {item.strip().lower() for item in (getattr(user, "roles", "") or "").split(",")}
    if "admin" in roles or "administrator" in roles:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    real_ip = request.headers.get("x-real-ip", "")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else ""
