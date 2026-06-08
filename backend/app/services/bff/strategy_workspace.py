from __future__ import annotations

import logging
import time
from typing import Callable, TypeVar

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.timezone import beijing_now_string
from app.models.entities import User
from app.models.schema_defs.backtest import BacktestVerdictThresholdOut, BacktestVerdictThresholdsResponse
from app.models.schema_defs.bff import BffPartialError, StrategyWorkspaceBffResponse
from app.services.backtest_job_service import BacktestJobService
from app.services.bff.timeout import run_workspace_with_timeout
from app.services.low_buy.strategy_parameter_defaults import BACKTEST_EXECUTION_DEFAULTS
from app.services.quant.runtime_parameters import get_backtest_verdict_thresholds
from app.services.read_models.live_quote_overlay import apply_strategy_tracking_live_overlay
from app.services.strategy_metadata_service import StrategyMetadataService
from app.services.strategy_tracking import StrategyTrackingService

T = TypeVar("T")
logger = logging.getLogger(__name__)
STRATEGY_TRACKING_BFF_LIMIT = 50
STRATEGY_TRACKING_BFF_RANGE_DAYS = 60
STRATEGY_WORKSPACE_SOURCE_TIMEOUT_MS = {
    "strategy_tracking_items": 4_000,
    "strategy_meta": 1_000,
    "presets": 1_000,
    "recent_runs": 1_000,
    "verdict_thresholds": 500,
}


def build_strategy_workspace(
    db: Session,
    *,
    current_user: User,
    run_limit: int,
) -> StrategyWorkspaceBffResponse:
    """Build the StrategyHub first-screen payload behind one BFF seam."""

    errors: list[BffPartialError] = []
    tracking = _safe_budgeted(
        "strategy_tracking_items",
        errors,
        lambda: _run_db_source(
            db,
            lambda source_db: apply_strategy_tracking_live_overlay(
                StrategyTrackingService(source_db).list_items(
                    range_days=STRATEGY_TRACKING_BFF_RANGE_DAYS,
                    board_filter="include_all",
                    limit=STRATEGY_TRACKING_BFF_LIMIT,
                    offset=0,
                    sort="max_gain_desc",
                )
            ),
        ),
    )
    return StrategyWorkspaceBffResponse(
        generated_at=beijing_now_string(),
        strategy_meta=_safe_budgeted(
            "strategy_meta",
            errors,
            lambda: _run_db_source(
                db,
                lambda source_db: StrategyMetadataService(source_db).list_strategy_meta(current_user=current_user, include_hidden=False),
            ),
        ),
        presets=_safe_budgeted("presets", errors, lambda: _run_db_source(db, lambda source_db: StrategyMetadataService(source_db).list_presets())),
        recent_runs=_safe_budgeted(
            "recent_runs",
            errors,
            lambda: _run_db_source(
                db,
                lambda source_db: BacktestJobService(source_db).list_runs(
                    owner_user_id=current_user.id,
                    is_admin=False,
                    limit=run_limit,
                    offset=0,
                ),
            ),
        ),
        verdict_thresholds=_safe_budgeted("verdict_thresholds", errors, _verdict_thresholds),
        items=[] if tracking is None else tracking.items,
        total=0 if tracking is None else tracking.total,
        limit=STRATEGY_TRACKING_BFF_LIMIT if tracking is None else tracking.limit,
        offset=0 if tracking is None else tracking.offset,
        sort="max_gain_desc" if tracking is None else tracking.sort,
        summary=None if tracking is None else tracking.summary,
        performance=[] if tracking is None else tracking.performance,
        market_segments=[] if tracking is None else tracking.market_segments,
        shadow_observations=[] if tracking is None else tracking.shadow_observations,
        tracking_notes=[] if tracking is None else tracking.notes,
        partial_errors=errors,
    )


def _verdict_thresholds() -> BacktestVerdictThresholdsResponse:
    defaults = dict(BACKTEST_EXECUTION_DEFAULTS.get("verdict_thresholds") or {})
    current = get_backtest_verdict_thresholds()
    merged = {}
    for tier in ("light", "full", "walk_forward"):
        fallback = defaults.get(tier) or {}
        values = current.get(tier) if isinstance(current.get(tier), dict) else {}
        merged[tier] = BacktestVerdictThresholdOut(
            min_return_pct=float(values.get("min_return_pct", fallback.get("min_return_pct", 0.0))),
            min_sharpe=float(values.get("min_sharpe", fallback.get("min_sharpe", 0.0))),
            max_drawdown_pct=float(values.get("max_drawdown_pct", fallback.get("max_drawdown_pct", 0.0))),
            cautious_min_return_pct=float(
                values.get("cautious_min_return_pct", fallback.get("cautious_min_return_pct", 0.0))
            ),
            cautious_max_drawdown_pct=float(
                values.get("cautious_max_drawdown_pct", fallback.get("cautious_max_drawdown_pct", 0.0))
            ),
        )
    return BacktestVerdictThresholdsResponse(thresholds=merged)


def _safe(source: str, errors: list[BffPartialError], loader: Callable[[], T]) -> T | None:
    try:
        return loader()
    except Exception:
        errors.append(BffPartialError(source=source, detail="数据暂时不可用"))
        return None


def _safe_budgeted(source: str, errors: list[BffPartialError], loader: Callable[[], T]) -> T | None:
    timeout_ms = int(STRATEGY_WORKSPACE_SOURCE_TIMEOUT_MS.get(source) or 0)
    if timeout_ms <= 0:
        return _safe(source, errors, loader)
    started = time.perf_counter()
    return run_workspace_with_timeout(
        source=source,
        timeout_seconds=timeout_ms / 1000.0,
        loader=loader,
        fallback=lambda error: _record_timeout(
            source,
            errors,
            timeout_ms=error.timeout_ms or timeout_ms,
            started=started,
        ),
    )


def _record_timeout(
    source: str,
    errors: list[BffPartialError],
    *,
    timeout_ms: int,
    started: float,
) -> None:
    errors.append(
        BffPartialError(
            source=source,
            detail="数据源超时，已返回首屏可用的降级结果",
            reason="timeout",
            timeout_ms=timeout_ms,
            fallback_source="python_local",
            message="workspace source timeout",
            elapsed_ms=max(0, int((time.perf_counter() - started) * 1000)),
        )
    )
    logger.warning("strategy workspace source timed out source=%s timeout_ms=%s", source, timeout_ms)
    return None


def _run_db_source(db: Session, loader: Callable[[Session], T]) -> T:
    if not _threaded_db_source_allowed(db):
        return loader(db)
    with SessionLocal() as source_db:
        return loader(source_db)


def _threaded_db_source_allowed(db: Session) -> bool:
    try:
        url = str(db.get_bind().url)
    except Exception:
        return False
    return url not in {"sqlite:///:memory:", "sqlite://"}
