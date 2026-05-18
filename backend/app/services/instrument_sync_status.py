from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.timezone import beijing_now_string
from app.models.entities import SystemSetting


LATEST_KEY = "instruments.sync.latest"
RUN_KEY_PREFIX = "instruments.sync."


class InstrumentSyncStatusService:
    def start(self, *, kind: str) -> str:
        run_id = uuid4().hex
        self.update(
            run_id=run_id,
            kind=kind,
            status="queued",
            progress_pct=2.0,
            message="股票库更新任务已提交，等待后台执行",
        )
        return run_id

    def update(
        self,
        *,
        run_id: str,
        kind: str,
        status: str,
        progress_pct: float,
        message: str,
        result: dict[str, int] | None = None,
        error: str = "",
        task_id: int | None = None,
    ) -> None:
        payload = {
            "run_id": run_id,
            "kind": kind,
            "status": status,
            "progress_pct": max(0.0, min(float(progress_pct), 100.0)),
            "message": message,
            "result": result or {},
            "error": error,
            "task_id": task_id,
            "updated_at": beijing_now_string(),
        }
        _write_payload(payload)

    def finish(self, *, run_id: str, kind: str, result: dict[str, int]) -> None:
        total = sum(int(value or 0) for value in result.values())
        self.update(
            run_id=run_id,
            kind=kind,
            status="succeeded",
            progress_pct=100.0,
            message=f"股票库更新完成，共同步 {total} 条",
            result=result,
        )

    def fail(self, *, run_id: str, kind: str, error: str) -> None:
        self.update(
            run_id=run_id,
            kind=kind,
            status="failed",
            progress_pct=100.0,
            message="股票库更新失败",
            error=error,
        )

    def get(self, *, run_id: str | None = None) -> dict[str, Any]:
        with SessionLocal() as db:
            key = _run_key(run_id) if run_id else LATEST_KEY
            row = db.execute(select(SystemSetting).where(SystemSetting.key == key)).scalar_one_or_none()
            if row is None or not row.value:
                return _empty_status(run_id=run_id or "")
            try:
                payload = json.loads(row.value)
            except Exception:
                return _empty_status(run_id=run_id or "")
            return payload if isinstance(payload, dict) else _empty_status(run_id=run_id or "")


def _write_payload(payload: dict[str, Any]) -> None:
    raw = json.dumps(payload, ensure_ascii=False, default=str)
    with SessionLocal() as db:
        for key in (LATEST_KEY, _run_key(str(payload.get("run_id") or ""))):
            if not key:
                continue
            row = db.execute(select(SystemSetting).where(SystemSetting.key == key)).scalar_one_or_none()
            if row is None:
                db.add(SystemSetting(key=key, value=raw))
            else:
                row.value = raw
        db.commit()


def _run_key(run_id: str | None) -> str:
    safe_run_id = (run_id or "").strip()[:32]
    return f"{RUN_KEY_PREFIX}{safe_run_id}" if safe_run_id else ""


def _empty_status(*, run_id: str = "") -> dict[str, Any]:
    return {
        "run_id": run_id,
        "kind": "all",
        "status": "idle",
        "progress_pct": 0.0,
        "message": "尚未开始更新",
        "result": {},
        "error": "",
        "task_id": None,
        "updated_at": datetime.min.isoformat(),
    }
