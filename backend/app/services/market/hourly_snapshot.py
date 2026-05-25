from __future__ import annotations

import json
from datetime import datetime, time as dt_time
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.timezone import BEIJING_TZ, beijing_now, beijing_now_string
from app.models.entities import SystemSetting
from app.models.schemas import QuoteSnapshot
from app.services.market_data import MarketDataService
from app.services.market.trading_calendar import is_a_share_trading_day

SETTING_KEY = "market.hourly_all_a_snapshot"
_RUN_WINDOW_MINUTES = 5
_SNAPSHOT_SLOTS = (
    dt_time(9, 30),
    dt_time(10, 30),
    dt_time(11, 30),
    dt_time(13, 0),
    dt_time(14, 0),
    dt_time(15, 0),
)


class HourlyAllMarketSnapshotService:
    """Refresh one full A-share intraday snapshot and store a compact pulse."""

    def __init__(self, db: Session, market_data: MarketDataService | None = None) -> None:
        self.db = db
        self.market_data = market_data or MarketDataService()

    def refresh(self, *, reason: str = "scheduled_hourly") -> dict[str, Any]:
        snapshots = self.market_data.get_stock_spot_snapshot_map(force_refresh=True)
        payload = self._build_payload(snapshots, reason=reason)
        _write_state(self.db, payload)
        self.db.commit()
        return payload

    def _build_payload(self, snapshots: dict[str, QuoteSnapshot], *, reason: str) -> dict[str, Any]:
        values = [item for item in snapshots.values() if float(getattr(item, "last_price", 0.0) or 0.0) > 0]
        changes = [float(item.change_pct or 0.0) for item in values]
        count = len(changes)
        up_count = sum(1 for item in changes if item > 0)
        down_count = sum(1 for item in changes if item < 0)
        flat_count = max(count - up_count - down_count, 0)
        median_change = _median(changes)
        strong_count = sum(1 for item in changes if item >= 3.0)
        weak_count = sum(1 for item in changes if item <= -3.0)
        strength_score = _strength_score(up_count, down_count, strong_count, weak_count, count)
        return {
            "ok": count > 0,
            "reason": reason,
            "updated_at": beijing_now_string(),
            "snapshot_count": count,
            "stock_up_ratio": round(up_count / count, 4) if count else 0.0,
            "stock_down_ratio": round(down_count / count, 4) if count else 0.0,
            "stock_flat_count": flat_count,
            "stock_median_change": round(median_change, 4),
            "strong_count": strong_count,
            "weak_count": weak_count,
            "market_strength_score": strength_score,
            "market_strength_text": _strength_text(strength_score, count),
            "source": "eastmoney_all_a_spot",
            "data_quality_text": "全 A 股小时级快照已更新" if count else "全 A 股小时级快照暂不可用",
        }


def latest_hourly_all_market_snapshot(db: Session) -> dict[str, Any]:
    return _read_state(db)


def hourly_all_market_snapshot_due(now: datetime | None = None) -> bool:
    current = _normalize_beijing(now)
    if not is_a_share_trading_day(current.date()):
        return False
    current_minutes = current.hour * 60 + current.minute
    return any(
        0 <= current_minutes - (slot.hour * 60 + slot.minute) < _RUN_WINDOW_MINUTES
        for slot in _SNAPSHOT_SLOTS
    )


def hourly_all_market_snapshot_bucket(now: datetime | None = None) -> str:
    current = _normalize_beijing(now)
    current_minutes = current.hour * 60 + current.minute
    eligible = [
        slot
        for slot in _SNAPSHOT_SLOTS
        if 0 <= current_minutes - (slot.hour * 60 + slot.minute) < _RUN_WINDOW_MINUTES
    ]
    if eligible:
        slot = eligible[0]
        return f"{current:%Y%m%d}{slot.hour:02d}{slot.minute:02d}"
    return current.strftime("%Y%m%d%H")


def _normalize_beijing(value: datetime | None) -> datetime:
    current = value or beijing_now()
    if current.tzinfo is None:
        return current.replace(tzinfo=BEIJING_TZ)
    return current.astimezone(BEIJING_TZ)


def _read_state(db: Session) -> dict[str, Any]:
    row = db.execute(select(SystemSetting).where(SystemSetting.key == SETTING_KEY)).scalar_one_or_none()
    if row is None or not row.value:
        return {}
    try:
        value = json.loads(row.value)
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _write_state(db: Session, payload: dict[str, Any]) -> None:
    row = db.execute(select(SystemSetting).where(SystemSetting.key == SETTING_KEY)).scalar_one_or_none()
    raw = json.dumps(payload, ensure_ascii=False, default=str)
    if row is None:
        db.add(SystemSetting(key=SETTING_KEY, value=raw))
    else:
        row.value = raw
    db.flush()


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def _strength_score(up_count: int, down_count: int, strong_count: int, weak_count: int, total: int) -> float:
    if total <= 0:
        return 0.0
    breadth = (up_count - down_count) / total * 60
    tail = (strong_count - weak_count) / total * 40
    return round(max(-100.0, min(100.0, breadth + tail)), 2)


def _strength_text(score: float, count: int) -> str:
    if count <= 0:
        return "市场强弱待确认"
    if score >= 35:
        return "全市场偏强，可关注主线扩散与承接"
    if score >= 10:
        return "全市场温和修复，优先确认强结构"
    if score <= -35:
        return "全市场明显偏弱，控制新开仓"
    if score <= -10:
        return "全市场偏弱，等待午后或尾盘确认"
    return "全市场强弱中性，按信号质量筛选"
