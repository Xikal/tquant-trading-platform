from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import SystemSetting

SETTING_KEY = "bar_refresh_checkpoint"


@dataclass(frozen=True)
class DailyBarRefreshCheckpoint:
    trade_date: str
    limit: int
    chunk_size: int
    total_chunks: int
    last_chunk_index: int = -1
    updated: int = 0
    skipped: int = 0
    status: str = "running"

    @property
    def next_chunk_index(self) -> int:
        if self.status == "completed":
            return self.total_chunks
        return max(self.last_chunk_index + 1, 0)

    @property
    def completed(self) -> bool:
        return self.status == "completed"


class DailyBarRefreshCheckpointStore:
    def __init__(self, db: Session) -> None:
        self.db = db

    def load(self, *, trade_date: str, limit: int, chunk_size: int, total_chunks: int) -> DailyBarRefreshCheckpoint | None:
        row = self.db.execute(select(SystemSetting).where(SystemSetting.key == SETTING_KEY)).scalar_one_or_none()
        payload = _decode_payload(row.value if row else "")
        if not payload:
            return None
        checkpoint = DailyBarRefreshCheckpoint(
            trade_date=str(payload.get("trade_date") or ""),
            limit=int(payload.get("limit") or 0),
            chunk_size=int(payload.get("chunk_size") or 0),
            total_chunks=int(payload.get("total_chunks") or 0),
            last_chunk_index=int(payload.get("last_chunk_index") if payload.get("last_chunk_index") is not None else -1),
            updated=int(payload.get("updated") or 0),
            skipped=int(payload.get("skipped") or 0),
            status=str(payload.get("status") or "running"),
        )
        if checkpoint.trade_date != trade_date or checkpoint.limit != limit or checkpoint.chunk_size != chunk_size:
            return None
        if checkpoint.total_chunks != total_chunks:
            return None
        return checkpoint

    def save(self, checkpoint: DailyBarRefreshCheckpoint) -> None:
        payload = {
            "trade_date": checkpoint.trade_date,
            "limit": checkpoint.limit,
            "chunk_size": checkpoint.chunk_size,
            "total_chunks": checkpoint.total_chunks,
            "last_chunk_index": checkpoint.last_chunk_index,
            "updated": checkpoint.updated,
            "skipped": checkpoint.skipped,
            "status": checkpoint.status,
            "updated_at": datetime.utcnow().isoformat(timespec="seconds"),
        }
        row = self.db.execute(select(SystemSetting).where(SystemSetting.key == SETTING_KEY)).scalar_one_or_none()
        if row is None:
            self.db.add(SystemSetting(key=SETTING_KEY, value=json.dumps(payload, ensure_ascii=False)))
            return
        row.value = json.dumps(payload, ensure_ascii=False)


def _decode_payload(raw: str) -> dict[str, Any]:
    try:
        value = json.loads(raw or "{}")
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}
