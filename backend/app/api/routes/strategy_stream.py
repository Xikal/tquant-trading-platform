from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import SessionLocal
from app.models.backtest_entities import BacktestOptimization, BacktestValidation
from app.models.entities import User
from app.models.market_entities import BacktestRun
from app.services.sse_token_service import SseStreamTokenService

router = APIRouter(prefix="/strategy")
ws_router = APIRouter(prefix="/ws/strategy")
stream_tokens = SseStreamTokenService(ttl_seconds=60, scope="strategy-progress")

TERMINAL_STATUSES = {"completed", "succeeded", "failed", "cancelled", "deleted", "timeout"}


@router.post("/stream-token")
def create_strategy_stream_token(current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    grant = stream_tokens.issue(int(current_user.id))
    return {"stream_token": grant.token, "expires_in": stream_tokens.ttl_seconds}


@ws_router.websocket("/{task_type}/{task_id}")
async def stream_strategy_task_progress(
    websocket: WebSocket,
    task_type: str,
    task_id: int,
    stream_token: str = Query(default=""),
    interval_seconds: int = Query(default=3, ge=2, le=30),
) -> None:
    """Polling-based progress stream over WebSocket.

    This endpoint intentionally avoids an external event queue in Phase 3.  It
    keeps one DB session per connection and sends lightweight ping frames so
    clients can detect stalled/disconnected streams.
    """

    user_id = stream_tokens.consume(stream_token)
    if user_id is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    await websocket.accept()
    db = SessionLocal()
    try:
        while True:
            payload = _load_task_progress(db, task_type, task_id, int(user_id))
            if payload is None:
                await _send_json(websocket, {
                    "type": "error",
                    "code": "TASK_NOT_FOUND",
                    "message": "任务不存在或无权查看。",
                    "task_type": task_type,
                    "task_id": task_id,
                })
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
            await _send_json(websocket, payload)
            if str(payload.get("status") or "").lower() in TERMINAL_STATUSES:
                await websocket.close(code=status.WS_1000_NORMAL_CLOSURE)
                return
            try:
                await asyncio.wait_for(websocket.receive(), timeout=interval_seconds)
            except asyncio.TimeoutError:
                await _send_json(websocket, {
                    "type": "ping",
                    "task_type": task_type,
                    "task_id": task_id,
                    "server_time": datetime.utcnow().isoformat(),
                })
    except WebSocketDisconnect:
        return
    finally:
        db.close()


def _load_task_progress(db: Session, task_type: str, task_id: int, user_id: int) -> dict[str, Any] | None:
    model = _task_model(task_type)
    if model is None:
        return None
    db.expire_all()
    task = db.get(model, task_id)
    if task is None or not _user_can_view(db, task, user_id):
        return None
    status_text = str(getattr(task, "status", "") or "")
    progress = float(getattr(task, "progress_pct", 0.0) or 0.0)
    message = getattr(task, "error_message", "") or _progress_message(task_type, status_text, progress)
    return {
        "type": "progress",
        "task_type": task_type,
        "task_id": task_id,
        "status": status_text,
        "progress_pct": max(0.0, min(progress, 100.0)),
        "message": message,
        "updated_at": _iso_datetime(getattr(task, "updated_at", None)),
        "completed": status_text.lower() in TERMINAL_STATUSES,
    }


async def _send_json(websocket: WebSocket, payload: dict[str, Any]) -> None:
    await websocket.send_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def _task_model(task_type: str):
    return {
        "backtest": BacktestRun,
        "optimize": BacktestOptimization,
        "optimization": BacktestOptimization,
        "validate": BacktestValidation,
        "validation": BacktestValidation,
    }.get(task_type)


def _user_can_view(db: Session, task: Any, user_id: int) -> bool:
    owner = getattr(task, "owner_user_id", None)
    if owner is None:
        return False
    user = db.get(User, user_id)
    if user is not None and _is_admin(user):
        return True
    return int(owner) == int(user_id)


def _is_admin(user: User) -> bool:
    roles = {item.strip().lower() for item in (getattr(user, "roles", "") or "").split(",")}
    return "admin" in roles or "administrator" in roles


def _progress_message(task_type: str, status_text: str, progress: float) -> str:
    if status_text in {"completed", "succeeded"}:
        return "任务已完成。"
    if status_text == "failed":
        return "任务失败，请查看错误信息。"
    if status_text in {"cancelled", "deleted"}:
        return "任务已终止。"
    if status_text == "running":
        return f"{_task_label(task_type)}运行中，进度 {progress:.0f}%"
    return f"{_task_label(task_type)}等待执行。"


def _task_label(task_type: str) -> str:
    return {
        "backtest": "回测任务",
        "optimize": "参数优化",
        "optimization": "参数优化",
        "validate": "样本外验证",
        "validation": "样本外验证",
    }.get(task_type, "策略任务")


def _iso_datetime(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return ""
