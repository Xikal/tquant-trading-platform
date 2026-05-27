from __future__ import annotations

import hashlib
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


def _materialization_run_key(*, expected: str, strategies: list[str], limit: int, scan_limit: int) -> str:
    raw = "|".join(
        [
            expected,
            ",".join(strategies),
            str(max(1, min(int(limit or DEFAULT_LIMIT), 500))),
            str(max(1, min(int(scan_limit or DEFAULT_SCAN_LIMIT), 10000))),
        ]
    )
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    return f"{TASK_TYPE}:{expected}:{digest}"


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


def enqueue_low_buy_materialization_run(
    db: Session,
    *,
    strategies: list[str],
    limit: int,
    scan_limit: int,
    reason: str,
) -> dict[str, Any]:
    required = sorted({item.strip() for item in strategies if item and item.strip()})
    expected = expected_low_buy_trade_date(db)
    active_limit = max(1, min(int(limit or DEFAULT_LIMIT), 500))
    active_scan_limit = max(1, min(int(scan_limit or DEFAULT_SCAN_LIMIT), 10000))
    task = RuntimeTaskQueue(db).enqueue(
        RuntimeTaskCreate(
            task_type=TASK_TYPE,
            payload={
                "expected_trade_date": expected,
                "strategies": required,
                "limit": active_limit,
                "scan_limit": active_scan_limit,
                "reason": reason,
            },
            priority=30,
            idempotency_key=_materialization_run_key(
                expected=expected,
                strategies=required,
                limit=active_limit,
                scan_limit=active_scan_limit,
            ),
            max_attempts=2,
        )
    )
    return {
        "ok": True,
        "accepted": True,
        "job_id": str(task.id),
        "task_type": TASK_TYPE,
        "expected_trade_date": expected,
        "status": task.status,
    }


def refresh_latest_low_buy_materialization(
    *,
    limit: int = DEFAULT_LIMIT,
    scan_limit: int = DEFAULT_SCAN_LIMIT,
    strategies: list[str] | None = None,
    prefer_go: bool = True,
) -> dict[str, Any]:
    required = sorted(strategies or (PRODUCTION_PRIORITY_STRATEGIES | OBSERVATION_LAYER_STRATEGIES))
    if prefer_go:
        from app.services.low_buy.go_scan_worker import run_go_scan_worker

        go_result = run_go_scan_worker(
            strategies=required,
            scan_limit=scan_limit,
            limit=limit,
            reason="latest_low_buy_materialization",
        )
        if go_result.get("ok"):
            return {**go_result, "source": "go_scan_worker"}

    return _refresh_latest_low_buy_materialization_python(
        limit=limit,
        scan_limit=scan_limit,
        strategies=required,
        fallback_reason=None if not prefer_go else go_result.get("fallback_reason", "go_scan_worker_unavailable"),
    )


def _refresh_latest_low_buy_materialization_python(
    *,
    limit: int,
    scan_limit: int,
    strategies: list[str],
    fallback_reason: str | None = None,
) -> dict[str, Any]:
    from app.services.low_buy_screener import LowBuyScreenerService

    screener = LowBuyScreenerService()
    refreshed: list[str] = []
    skipped: list[dict[str, str]] = []
    for strategy in strategies:
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
        status = publish_latest_trade_date_if_ready(db, strategies=strategies)
        db.commit()
    return {
        "ok": not skipped,
        "source": "python_fallback" if fallback_reason else "python",
        "fallback_reason": fallback_reason or "",
        "refreshed": refreshed,
        "skipped": skipped,
        "publish_status": status,
    }
