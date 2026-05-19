from __future__ import annotations

import json
from datetime import datetime, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.timezone import beijing_today
from app.models.entities import PaperOrder

_DEDUP_EXIT_CODES = {
    "hard_stop_loss",
    "etf_stop_loss",
    "time_exit",
    "weak_hold_exit",
    "etf_time_exit",
}


def duplicate_auto_exit_exists(
    db: Session,
    *,
    account_id: int,
    symbol: str,
    side: str,
    source: str,
    signal_snapshot: dict,
) -> bool:
    if side != "sell" or source != "auto_exit":
        return False
    exit_code = str(signal_snapshot.get("exit_code") or "").strip()
    if exit_code not in _DEDUP_EXIT_CODES:
        return False
    start = datetime.combine(beijing_today(), time.min)
    end = datetime.combine(beijing_today(), time.max)
    rows = (
        db.execute(
            select(PaperOrder.signal_snapshot)
            .where(
                PaperOrder.account_id == account_id,
                PaperOrder.symbol == symbol,
                PaperOrder.side == "sell",
                PaperOrder.source == "auto_exit",
                PaperOrder.status.in_(["pending", "partial", "filled"]),
                PaperOrder.created_at >= start,
                PaperOrder.created_at < end,
            )
            .limit(20)
        )
        .scalars()
        .all()
    )
    return any(_exit_code(row) == exit_code for row in rows)


def _exit_code(payload_json: str | None) -> str:
    try:
        payload = json.loads(payload_json or "{}")
    except Exception:
        return ""
    return str(payload.get("exit_code") or "").strip() if isinstance(payload, dict) else ""

