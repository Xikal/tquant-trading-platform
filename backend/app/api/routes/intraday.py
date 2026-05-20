from __future__ import annotations

import asyncio
import json
from datetime import datetime
import time

from fastapi import APIRouter, Depends, Header, Query
from fastapi import HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, get_db
from app.core.auth import get_current_user
from app.models.entities import SseSubscription, UserWatchlist
from app.models.entities import User
from app.models.schemas import IntradayConfirmationOut, IntradayConfirmationRequest
from app.services.intraday_confirmation_service import IntradayConfirmationService
from app.models.schema_defs.agent import AgentNotificationTestRequest
from app.services.agent_notification_service import AgentNotificationService
from app.services.intraday_key_levels import IntradayKeyLevelService
from app.services.sse_token_service import SseStreamTokenService

router = APIRouter(prefix="/intraday")
stream_tokens = SseStreamTokenService(ttl_seconds=3600)
key_level_service = IntradayKeyLevelService()


@router.post("/confirmations", response_model=list[IntradayConfirmationOut])
def build_intraday_confirmations(
    payload: IntradayConfirmationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[IntradayConfirmationOut]:
    return IntradayConfirmationService(db).confirm_symbols(
        payload.symbols,
        period=payload.period,
        limit=payload.limit,
    )


@router.get("/confirmations", response_model=list[IntradayConfirmationOut])
def list_intraday_confirmations(
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[IntradayConfirmationOut]:
    return IntradayConfirmationService(db).list_recent(limit=limit)


@router.post("/subscribe")
def create_intraday_stream_subscription(
    current_user: User = Depends(get_current_user),
) -> dict:
    grant = stream_tokens.issue(int(current_user.id))
    return {
        "stream_token": grant.token,
        "expires_in": stream_tokens.ttl_seconds,
    }


@router.get("/stream")
def stream_intraday_confirmations(
    symbols: str = Query(default=""),
    client_id: str = Query(default="web"),
    stream_token: str = Query(default=""),
    last_event_id: str = Query(default=""),
    last_event_id_header: str = Header(default="", alias="Last-Event-ID"),
    interval_seconds: int = Query(default=15, ge=5, le=120),
):
    user_id = _user_id_from_stream_token(stream_token)
    symbol_list = [item.strip() for item in symbols.split(",") if item.strip()]
    return StreamingResponse(
        _confirmation_event_stream(symbol_list, client_id, user_id, interval_seconds, last_event_id or last_event_id_header),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/key-levels/stream")
def stream_intraday_key_levels(
    symbols: str = Query(default=""),
    entry_zones: str = Query(default=""),
    client_id: str = Query(default="web"),
    stream_token: str = Query(default=""),
    interval_seconds: int = Query(default=20, ge=10, le=120),
    feishu: bool = Query(default=False),
):
    user_id = _user_id_from_stream_token(stream_token)
    symbol_list = [item.strip() for item in symbols.split(",") if item.strip()]
    entry_zone_map = _parse_entry_zones(entry_zones)
    return StreamingResponse(
        _key_level_event_stream(symbol_list, entry_zone_map, client_id, user_id, interval_seconds, feishu),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _confirmation_event_stream(
    symbols: list[str],
    client_id: str,
    user_id: int,
    interval_seconds: int,
    last_event_id: str = "",
):
    _touch_subscription(client_id, "intraday_confirmations", user_id)
    while True:
        with SessionLocal() as db:
            target_symbols = symbols or _user_watchlist_symbols(db, user_id)
            if target_symbols:
                items = IntradayConfirmationService(db).confirm_symbols(target_symbols, period="1m", limit=120)
            else:
                items = IntradayConfirmationService(db).list_recent(limit=50)
        payload = json.dumps(
            {
                "type": "intraday_confirmations",
                "last_event_id": last_event_id,
                "items": [item.model_dump(mode="json") for item in items],
            },
            ensure_ascii=False,
            default=str,
        )
        event_id = f"{user_id}-{int(time.time())}"
        yield f"id: {event_id}\nevent: intraday_confirmations\ndata: {payload}\n\n"
        await asyncio.sleep(interval_seconds)


async def _key_level_event_stream(
    symbols: list[str],
    entry_zone_map: dict[str, tuple[float | None, float | None]],
    client_id: str,
    user_id: int,
    interval_seconds: int,
    feishu: bool,
):
    _touch_subscription(client_id, "intraday_key_levels", user_id)
    notified: set[str] = set()
    while True:
        with SessionLocal() as db:
            target_symbols = symbols or _user_watchlist_symbols(db, user_id)
        items = [
            key_level_service.build(
                symbol,
                entry_zone_low=entry_zone_map.get(symbol, (None, None))[0],
                entry_zone_high=entry_zone_map.get(symbol, (None, None))[1],
            )
            for symbol in target_symbols[:20]
        ]
        alerts = [item for item in items if item.alert_triggered]
        if feishu:
            _notify_key_level_alerts(alerts, notified)
        payload = json.dumps(
            {
                "type": "intraday_key_levels",
                "items": [item.model_dump(mode="json") for item in items],
                "alerts": [item.model_dump(mode="json") for item in alerts],
            },
            ensure_ascii=False,
            default=str,
        )
        event_id = f"{user_id}-levels-{int(time.time())}"
        yield f"id: {event_id}\nevent: intraday_key_levels\ndata: {payload}\n\n"
        await asyncio.sleep(interval_seconds)


def _touch_subscription(client_id: str, channel: str, user_id: int) -> None:
    with SessionLocal() as db:
        row = (
            db.execute(
                select(SseSubscription).where(
                    SseSubscription.client_id == client_id,
                    SseSubscription.channel == channel,
                )
            )
            .scalars()
            .first()
        )
        if row is None:
            row = SseSubscription(client_id=client_id, channel=channel, user_id=user_id, status="active")
            db.add(row)
        row.user_id = user_id
        row.last_seen_at = datetime.now()
        db.commit()


def _user_watchlist_symbols(db: Session, user_id: int) -> list[str]:
    rows = (
        db.execute(
            select(UserWatchlist.symbol)
            .where(UserWatchlist.user_id == user_id)
            .order_by(UserWatchlist.updated_at.desc())
            .limit(20)
        )
        .scalars()
        .all()
    )
    return [item for item in rows if item]


def _user_id_from_stream_token(stream_token: str) -> int:
    if not stream_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="SSE 订阅需要一次性连接令牌")
    user_id = stream_tokens.consume(stream_token)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="SSE 连接令牌无效或已过期")
    return int(user_id)


def _parse_entry_zones(raw: str) -> dict[str, tuple[float | None, float | None]]:
    result: dict[str, tuple[float | None, float | None]] = {}
    for chunk in (raw or "").split(";"):
        parts = [item.strip() for item in chunk.split(":")]
        if len(parts) != 3 or not parts[0]:
            continue
        try:
            result[parts[0]] = (float(parts[1]), float(parts[2]))
        except (TypeError, ValueError):
            continue
    return result


def _notify_key_level_alerts(alerts: list, notified: set[str]) -> None:
    for item in alerts[:5]:
        key = f"{item.symbol}:{item.alert_text}"
        if not item.alert_text or key in notified:
            continue
        notified.add(key)
        AgentNotificationService().send_test(
            AgentNotificationTestRequest(channel="feishu", message=f"盘中关键价位预警：{item.alert_text}")
        )
