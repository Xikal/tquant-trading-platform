from __future__ import annotations

from datetime import datetime

from app.core.database import SessionLocal
from app.core.timezone import beijing_now
from app.models.schema_defs.phase4 import RuntimeTaskCreate
from app.services.tasks import RuntimeTaskQueue


def enqueue_monthly_factor_mining_once(now: datetime | None = None):
    now = now or beijing_now()
    if now.day != 1 or now.hour < 17:
        return None
    bucket = now.strftime("%Y%m")
    with SessionLocal() as db:
        return RuntimeTaskQueue(db).enqueue(
            RuntimeTaskCreate(
                task_type="factor_mining_monthly",
                payload={"topic": "A股低吸量价结构与情绪温度交叉因子", "count": 20},
                priority=210,
                idempotency_key=f"factor_mining_monthly:{bucket}",
                max_attempts=2,
            )
        )
