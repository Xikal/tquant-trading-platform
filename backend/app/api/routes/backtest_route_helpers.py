from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.role_permissions import ensure_permission, is_admin_user
from app.models.entities import User
from app.services.low_buy.strategy_parameter_defaults import BACKTEST_EXECUTION_DEFAULTS
from app.services.quant.runtime_parameters import get_backtest_verdict_thresholds
from app.services.strategy_metadata_service import StrategyMetadataService


def is_admin(user: User) -> bool:
    return is_admin_user(user)


def require_optimizer_access(user: User) -> None:
    ensure_permission(user, "optimizer")


def require_research_access(user: User) -> None:
    try:
        ensure_permission(user, "research")
    except HTTPException as exc:
        if exc.status_code == status.HTTP_403_FORBIDDEN:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号未开通样本外验证权限") from exc
        raise


def validate_backtest_strategy_access(db: Session, strategy_keys: list[str], user: User) -> None:
    try:
        StrategyMetadataService(db).validate_backtest_strategy_access(strategy_keys, current_user=user)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


def normalized_verdict_thresholds() -> dict[str, dict[str, float]]:
    defaults = dict(BACKTEST_EXECUTION_DEFAULTS.get("verdict_thresholds") or {})
    current = get_backtest_verdict_thresholds()
    merged = {}
    for tier in ("light", "full", "walk_forward"):
        fallback = defaults.get(tier) or {}
        values = current.get(tier) if isinstance(current.get(tier), dict) else {}
        merged[tier] = {
            "min_return_pct": float(values.get("min_return_pct", fallback.get("min_return_pct", 0.0))),
            "min_sharpe": float(values.get("min_sharpe", fallback.get("min_sharpe", 0.0))),
            "max_drawdown_pct": float(values.get("max_drawdown_pct", fallback.get("max_drawdown_pct", 0.0))),
            "cautious_min_return_pct": float(
                values.get("cautious_min_return_pct", fallback.get("cautious_min_return_pct", 0.0))
            ),
            "cautious_max_drawdown_pct": float(
                values.get("cautious_max_drawdown_pct", fallback.get("cautious_max_drawdown_pct", 0.0))
            ),
        }
    return merged
