from __future__ import annotations

from typing import Callable, TypeVar

from sqlalchemy.orm import Session

from app.core.timezone import beijing_now_string
from app.models.entities import User
from app.models.schema_defs.backtest import BacktestVerdictThresholdOut, BacktestVerdictThresholdsResponse
from app.models.schema_defs.bff import BffPartialError, StrategyWorkspaceBffResponse
from app.services.backtest_job_service import BacktestJobService
from app.services.low_buy.strategy_parameter_defaults import BACKTEST_EXECUTION_DEFAULTS
from app.services.quant.runtime_parameters import get_backtest_verdict_thresholds
from app.services.strategy_metadata_service import StrategyMetadataService

T = TypeVar("T")


def build_strategy_workspace(
    db: Session,
    *,
    current_user: User,
    run_limit: int,
) -> StrategyWorkspaceBffResponse:
    """Build the StrategyHub first-screen payload behind one BFF seam."""

    errors: list[BffPartialError] = []
    metadata = StrategyMetadataService(db)
    return StrategyWorkspaceBffResponse(
        generated_at=beijing_now_string(),
        strategy_meta=_safe(
            "strategy_meta",
            errors,
            lambda: metadata.list_strategy_meta(current_user=current_user, include_hidden=False),
        ),
        presets=_safe("presets", errors, metadata.list_presets),
        recent_runs=_safe(
            "recent_runs",
            errors,
            lambda: BacktestJobService(db).list_runs(
                owner_user_id=current_user.id,
                is_admin=False,
                limit=run_limit,
                offset=0,
            ),
        ),
        verdict_thresholds=_safe("verdict_thresholds", errors, _verdict_thresholds),
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
