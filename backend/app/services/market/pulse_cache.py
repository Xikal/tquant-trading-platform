from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.timezone import beijing_now, beijing_now_string
from app.models.entities import MarketPulseEvent
from app.models.schema_defs.market import IntradayMarketPulse

FRESH_SECONDS = 180


def latest_pulse_or_placeholder(
    db: Session,
    *,
    trade_date: str,
    fresh_seconds: int = FRESH_SECONDS,
) -> tuple[IntradayMarketPulse, bool]:
    row = db.execute(
        select(MarketPulseEvent)
        .where(MarketPulseEvent.trade_date == trade_date)
        .order_by(MarketPulseEvent.created_at.desc(), MarketPulseEvent.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    if row is None:
        return _placeholder(), True

    payload = _json_dict(row.payload_json)
    pulse = _pulse_from_row(row, payload)
    is_stale = _is_stale(getattr(row, "created_at", None), fresh_seconds=fresh_seconds)
    if is_stale and pulse.data_quality == "fresh":
        pulse = pulse.model_copy(
            update={
                "data_quality": "stale",
                "data_quality_text": "盘中 pulse 使用最近一次快照，后台正在刷新。",
                "partial_errors": [
                    *pulse.partial_errors,
                    {"source": "pulse_snapshot", "detail": "快照已过期，后台正在刷新"},
                ],
            }
        )
    return pulse, is_stale


def _pulse_from_row(row: MarketPulseEvent, payload: dict[str, Any]) -> IntradayMarketPulse:
    return IntradayMarketPulse.model_validate(
        {
            "updated_at": payload.get("updated_at") or beijing_now_string(),
            "data_quality": _quality(payload.get("data_quality") or row.data_quality),
            "data_quality_text": payload.get("data_quality_text") or "盘中 pulse 使用最近一次快照",
            "market_strength_text": payload.get("market_strength_text") or "市场强弱待确认",
            "leader_strength_text": payload.get("leader_strength_text") or "龙头强度待确认",
            "emotion_text": payload.get("emotion_text") or "情绪温度待确认",
            "hourly_snapshot_text": payload.get("hourly_snapshot_text") or "小时快照待确认",
            "pulse_level": payload.get("pulse_level") or row.pulse_level or "unknown",
            "pulse_text": payload.get("pulse_text") or row.pulse_text or "等待盘中数据刷新。",
            "suggested_action": payload.get("suggested_action") or row.suggested_action or "只读观察，不触发交易。",
            "partial_errors": _list_of_dicts(payload.get("partial_errors")),
            "market_breadth_summary": _dict_value(payload.get("market_breadth_summary")),
            "leader_strength_summary": _dict_value(payload.get("leader_strength_summary")),
            "emotion_summary": _dict_value(payload.get("emotion_summary")),
            "hourly_snapshot_summary": _dict_value(payload.get("hourly_snapshot_summary")),
            "autofill_details": _list_of_dicts(payload.get("autofill_details")),
        }
    )


def _placeholder() -> IntradayMarketPulse:
    return IntradayMarketPulse(
        updated_at=beijing_now_string(),
        data_quality="unavailable",
        data_quality_text="盘中 pulse 暂不可用",
        market_strength_text="市场强弱待确认",
        leader_strength_text="龙头强度待确认",
        emotion_text="情绪温度待确认",
        hourly_snapshot_text="小时快照待确认",
        pulse_level="unavailable",
        pulse_text="暂时没有可用的盘中 pulse。",
        suggested_action="等待后台刷新，不根据当前空数据加仓。",
        partial_errors=[{"source": "pulse_snapshot", "detail": "后台正在刷新盘中 pulse"}],
    )


def _is_stale(created_at: datetime | None, *, fresh_seconds: int) -> bool:
    if created_at is None:
        return True
    current = beijing_now()
    if created_at.tzinfo is None:
        current = current.replace(tzinfo=None)
    return current - created_at > timedelta(seconds=max(1, fresh_seconds))


def _json_dict(raw: str) -> dict[str, Any]:
    try:
        value = json.loads(raw or "{}")
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _quality(value: Any) -> str:
    raw = str(value or "").strip().lower()
    return raw if raw in {"fresh", "stale", "partial", "unavailable"} else "unavailable"

