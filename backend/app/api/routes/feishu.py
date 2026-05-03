from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.admin_auth import require_admin_auth
from app.core.database import get_db
from app.models.entities import UserFeishuBinding
from app.models.schema_defs.feishu import (
    FeishuBindingRequest,
    FeishuBindingResponse,
    FeishuEventResponse,
)
from app.services.feishu import FeishuAgentBridge, FeishuAppConfig

router = APIRouter(prefix="/feishu")
bridge = FeishuAgentBridge()


@router.get("/callback", response_model=FeishuEventResponse)
def feishu_callback(challenge: str = "") -> FeishuEventResponse:
    return FeishuEventResponse(ok=True, challenge=challenge, message="ok")


@router.post("/event", response_model=FeishuEventResponse)
def feishu_event(payload: dict[str, Any], db: Session = Depends(get_db)) -> FeishuEventResponse:
    _verify_event_token(payload)
    if payload.get("type") == "url_verification":
        return FeishuEventResponse(ok=True, challenge=str(payload.get("challenge") or ""))

    event = payload.get("event") if isinstance(payload.get("event"), dict) else {}
    sender = event.get("sender") if isinstance(event.get("sender"), dict) else {}
    message = event.get("message") if isinstance(event.get("message"), dict) else {}
    open_id = _extract_open_id(sender)
    text = _extract_text(message)
    response = bridge.handle_text(db, open_id=open_id, text=text)
    return FeishuEventResponse(ok=True, message="processed", response=response)


def _verify_event_token(payload: dict[str, Any]) -> None:
    token = str(payload.get("token") or "")
    header = payload.get("header") if isinstance(payload.get("header"), dict) else {}
    token = token or str(header.get("token") or "")
    if not FeishuAppConfig().verify_token(token):
        raise HTTPException(status_code=403, detail="飞书验证 token 不匹配")


@router.post("/bindings", response_model=FeishuBindingResponse)
def bind_feishu_user(
    payload: FeishuBindingRequest,
    _: None = Depends(require_admin_auth),
    db: Session = Depends(get_db),
) -> FeishuBindingResponse:
    row = (
        db.execute(select(UserFeishuBinding).where(UserFeishuBinding.open_id == payload.open_id))
        .scalars()
        .first()
    )
    if row is None:
        row = UserFeishuBinding(
            user_id=payload.user_id,
            open_id=payload.open_id,
            union_id=payload.union_id,
            tenant_key=payload.tenant_key,
        )
        db.add(row)
    else:
        row.user_id = payload.user_id
        row.union_id = payload.union_id or row.union_id
        row.tenant_key = payload.tenant_key or row.tenant_key
        row.status = "active"
    db.commit()
    db.refresh(row)
    return _binding_out(row)


def _extract_open_id(sender: dict[str, Any]) -> str:
    sender_id = sender.get("sender_id") if isinstance(sender.get("sender_id"), dict) else {}
    return str(sender_id.get("open_id") or sender.get("open_id") or "")


def _extract_text(message: dict[str, Any]) -> str:
    content = message.get("content")
    if isinstance(content, str):
        try:
            import json

            decoded = json.loads(content)
            return str(decoded.get("text") or "")
        except Exception:
            return content
    if isinstance(content, dict):
        return str(content.get("text") or "")
    return ""


def _binding_out(row: UserFeishuBinding) -> FeishuBindingResponse:
    return FeishuBindingResponse(
        id=row.id,
        user_id=row.user_id,
        open_id=row.open_id,
        tenant_key=row.tenant_key,
        status=row.status,
    )
