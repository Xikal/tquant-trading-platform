from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import PaperPosition, SystemSetting


def update_position_trailing_high(
    db: Session,
    *,
    account_id: int,
    position: PaperPosition,
    current_price: float,
) -> float:
    if current_price <= 0:
        return 0.0
    key = _setting_key(account_id, position.symbol)
    opened_at = _opened_at_key(position.opened_at)
    row = db.execute(select(SystemSetting).where(SystemSetting.key == key)).scalar_one_or_none()
    payload = _load_payload(row.value if row else "")
    previous_high = float(payload.get("high") or 0.0) if payload.get("opened_at") == opened_at else 0.0
    high_price = max(previous_high, current_price)
    raw = json.dumps({"opened_at": opened_at, "high": round(high_price, 4)}, ensure_ascii=False)
    if row is None:
        db.add(SystemSetting(key=key, value=raw))
    else:
        row.value = raw
    return high_price


def _setting_key(account_id: int, symbol: str) -> str:
    return f"paper_trail:{account_id}:{symbol}"[:64]


def _opened_at_key(value: datetime | None) -> str:
    return value.isoformat(timespec="seconds") if value else ""


def _load_payload(raw: str) -> dict[str, object]:
    try:
        payload = json.loads(raw or "{}")
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}
