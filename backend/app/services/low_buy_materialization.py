from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.schema_defs.phase4 import RuntimeTaskCreate
from app.services.latest_data_status import (
    expected_low_buy_trade_date,
    publish_latest_trade_date_if_ready,
)
from app.services.low_buy.strategy_policy import OBSERVATION_LAYER_STRATEGIES, PRODUCTION_PRIORITY_STRATEGIES
from app.services.tasks import RuntimeTaskQueue

DEFAULT_LIMIT = 40
DEFAULT_SCAN_LIMIT = 480
TASK_TYPE = "low_buy_materialization_refresh"


def enqueue_low_buy_materialization(db: Session, *, reason: str = "latest_data_required", commit: bool = False) -> None:
    expected = expected_low_buy_trade_date(db)
    RuntimeTaskQueue(db).enqueue(
        RuntimeTaskCreate(
            task_type=TASK_TYPE,
            payload={"expected_trade_date": expected, "reason": reason},
            priority=35,
            idempotency_key=f"{TASK_TYPE}:{expected}",
            max_attempts=2,
        )
    )
    if commit:
        db.commit()


def refresh_latest_low_buy_materialization(
    *,
    limit: int = DEFAULT_LIMIT,
    scan_limit: int = DEFAULT_SCAN_LIMIT,
    strategies: list[str] | None = None,
) -> dict[str, Any]:
    from app.services.low_buy_screener import LowBuyScreenerService

    required = sorted(strategies or (PRODUCTION_PRIORITY_STRATEGIES | OBSERVATION_LAYER_STRATEGIES))
    screener = LowBuyScreenerService()
    refreshed: list[str] = []
    skipped: list[dict[str, str]] = []
    for strategy in required:
        try:
            payload = screener.refresh_full_scan_cache(
                strategy=strategy,
                limit=limit,
                scan_limit=scan_limit,
                include_history=False,
                compute_performance=True,
                build_close_review=False,
            )
            refreshed.append(f"{strategy}:{payload.latest_trade_date}")
        except Exception as exc:
            skipped.append({"strategy": strategy, "reason": str(exc)})
    from app.core.database import SessionLocal

    with SessionLocal() as db:
        status = publish_latest_trade_date_if_ready(db, strategies=required)
        db.commit()
    return {
        "ok": not skipped,
        "refreshed": refreshed,
        "skipped": skipped,
        "publish_status": status,
    }
