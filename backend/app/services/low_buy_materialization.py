from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.schema_defs.phase4 import RuntimeTaskCreate
from app.services.latest_data_status import (
    expected_low_buy_trade_date,
    publish_latest_trade_date_if_ready,
)
from app.core.config import get_settings
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
            return {
                **go_result,
                "source": "go_scan_worker",
                "main_force_shadow": warm_main_force_shadow_observations(
                    strategies=required,
                    limit=limit,
                    scan_limit=scan_limit,
                    reason="go_scan_worker_shadow_warmup",
                ),
            }

    return _refresh_latest_low_buy_materialization_python(
        limit=limit,
        scan_limit=scan_limit,
        strategies=required,
        fallback_reason=None if not prefer_go else go_result.get("fallback_reason", "go_scan_worker_unavailable"),
    )


def warm_main_force_shadow_observations(
    *,
    strategies: list[str] | None = None,
    limit: int = DEFAULT_LIMIT,
    scan_limit: int = DEFAULT_SCAN_LIMIT,
    reason: str = "main_force_shadow_warmup",
) -> dict[str, Any]:
    settings = get_settings()
    if not settings.main_force_model_enabled or not settings.main_force_model_shadow_enabled:
        return {"ok": True, "enabled": False, "reason": "main_force_shadow_disabled", "strategies": []}

    allowed = _allowed_main_force_strategies(settings.main_force_model_allowed_strategies)
    required = sorted({item.strip() for item in (strategies or []) if item and item.strip()})
    selected = [strategy for strategy in required if strategy in allowed]
    if not selected:
        return {"ok": True, "enabled": True, "reason": "no_allowed_strategies", "strategies": []}

    # Keep this small: the purpose is to observe the readonly model path, not to
    # duplicate the full production materialization workload.
    active_limit = max(1, min(int(limit or DEFAULT_LIMIT), 80))
    active_scan_limit = max(1, min(int(scan_limit or DEFAULT_SCAN_LIMIT), 480))

    from app.services.low_buy.main_force_model_schema import MAIN_FORCE_MODEL_OBSERVATION_KEY
    from app.models.entities import MarketModelObservation
    from app.core.database import SessionLocal
    from sqlalchemy import func, select

    refreshed: list[str] = []
    skipped: list[dict[str, str]] = []
    with SessionLocal() as db:
        before = int(
            db.execute(
                select(func.count(MarketModelObservation.id)).where(
                    MarketModelObservation.model_key == MAIN_FORCE_MODEL_OBSERVATION_KEY
                )
            ).scalar()
            or 0
        )
        materialized = _warm_shadow_from_materialized_candidates(
            db,
            strategies=selected,
            limit=active_limit,
        )
        refreshed.extend(materialized["refreshed"])
        skipped.extend(materialized["skipped"])
        remaining = [strategy for strategy in selected if strategy not in materialized["strategies"]]
        if remaining:
            from app.services.low_buy_screener import LowBuyScreenerService

            screener = LowBuyScreenerService()
        else:
            screener = None
        for strategy in remaining:
            try:
                payload = screener._runtime._screen_sync(  # type: ignore[union-attr]
                    db=db,
                    strategy=strategy,
                    limit=active_limit,
                    scan_limit=active_scan_limit,
                    include_history=False,
                    scan_mode="full",
                    compute_performance=False,
                    history_wait_timeout_seconds=1.5,
                    bypass_cache=True,
                    record_shadow=True,
                )
                db.commit()
                refreshed.append(f"reference:{strategy}:{payload.latest_trade_date}:{payload.matched_count}")
            except Exception as exc:
                db.rollback()
                skipped.append({"strategy": strategy, "reason": str(exc)})
                continue
        after = int(
            db.execute(
                select(func.count(MarketModelObservation.id)).where(
                    MarketModelObservation.model_key == MAIN_FORCE_MODEL_OBSERVATION_KEY
                )
            ).scalar()
            or 0
        )

    return {
        "ok": not skipped,
        "enabled": True,
        "reason": reason,
        "strategies": selected,
        "refreshed": refreshed,
        "skipped": skipped,
        "record_count_before": before,
        "record_count_after": after,
        "records_added": max(0, after - before),
    }


def _warm_shadow_from_materialized_candidates(
    db: Any,
    *,
    strategies: list[str],
    limit: int,
) -> dict[str, Any]:
    from app.repositories.low_buy import DailyHistoryRepository, LowBuyResultRepository
    from app.models.schemas import LowBuyCandidateOut
    from app.services.low_buy.main_force_model_enrichment import enrich_candidates_with_main_force_model

    repository = LowBuyResultRepository(db)
    try:
        latest_trade_date = repository.fetch_latest_trade_date()
    except Exception:
        return {"strategies": [], "refreshed": [], "skipped": []}
    if not latest_trade_date:
        return {"strategies": [], "refreshed": [], "skipped": []}

    histories: dict[str, Any] = {}
    refreshed: list[str] = []
    skipped: list[dict[str, str]] = []
    completed: list[str] = []
    for strategy in strategies:
        summary = repository.fetch_scan_summary(latest_trade_date=latest_trade_date, strategy_key=strategy)
        if summary is None:
            continue
        rows = repository.fetch_results(
            latest_trade_date=latest_trade_date,
            strategy_key=strategy,
            limit=max(1, limit),
        )
        candidates = []
        for row in rows:
            try:
                candidates.append(LowBuyCandidateOut.model_validate_json(row.payload_json))
            except Exception:
                continue
        candidates = [
            candidate
            for candidate in candidates
            if candidate.buy_signal_state in {"buy_now", "soft_buy_now", "observe_confirmed", "near_entry"}
        ][: max(1, limit)]
        if not candidates:
            continue
        try:
            symbols = sorted({candidate.symbol for candidate in candidates if candidate.symbol})
            if symbols:
                histories = DailyHistoryRepository(db).fetch_rows_for_symbols(
                    symbols,
                    min(
                        str(getattr(candidate, "board_date", "") or latest_trade_date)[:10] or latest_trade_date
                        for candidate in candidates
                    ),
                    latest_trade_date,
                )
            filters = _safe_json_object(summary.filters_json)
            enrich_candidates_with_main_force_model(
                db,
                candidates=candidates,
                histories=histories,
                market_state=str(filters.get("market_state") or "unknown"),
                market_strength=_float(filters.get("market_state_strength")),
                record_shadow=True,
            )
            db.commit()
            completed.append(strategy)
            refreshed.append(f"materialized:{strategy}:{latest_trade_date}:{len(candidates)}")
        except Exception as exc:
            db.rollback()
            skipped.append({"strategy": strategy, "reason": str(exc)})
    return {"strategies": completed, "refreshed": refreshed, "skipped": skipped}


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


def _allowed_main_force_strategies(raw: str) -> set[str]:
    return {item.strip() for item in str(raw or "").split(",") if item.strip()}


def _safe_json_object(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    try:
        value = json.loads(str(raw or "{}"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
