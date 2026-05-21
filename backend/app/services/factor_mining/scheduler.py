from __future__ import annotations

from datetime import datetime

from app.core.database import SessionLocal
from app.core.timezone import beijing_now
from app.models.schema_defs.phase4 import RuntimeTaskCreate
from app.services.tasks import RuntimeTaskQueue

FACTOR_MINING_MONTHLY_TOPICS = (
    "A股低吸量价结构与情绪温度交叉因子",
    "涨停回调后分时承接与板块接力因子",
    "板块轮动、资金流和龙头相对强度因子",
    "事件驱动、公告异动和龙虎榜结构因子",
    "基本面稳定性与短线资金偏好的交叉因子",
    "做T VWAP 折价、洗盘量能释放和冲高兑现因子",
)


def enqueue_monthly_factor_mining_once(now: datetime | None = None):
    now = now or beijing_now()
    if now.day != 1 or now.hour < 17:
        return None
    bucket = now.strftime("%Y%m")
    with SessionLocal() as db:
        return RuntimeTaskQueue(db).enqueue(
            RuntimeTaskCreate(
                task_type="factor_mining_monthly",
                payload={"topic": monthly_factor_mining_topic(now), "count": 20},
                priority=210,
                idempotency_key=f"factor_mining_monthly:{bucket}",
                max_attempts=2,
            )
        )


def monthly_factor_mining_topic(now: datetime) -> str:
    index = (now.year * 12 + now.month - 1) % len(FACTOR_MINING_MONTHLY_TOPICS)
    return FACTOR_MINING_MONTHLY_TOPICS[index]
