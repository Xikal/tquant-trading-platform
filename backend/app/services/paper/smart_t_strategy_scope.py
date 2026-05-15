from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.strategy_metadata_service import StrategyMetadataService

_SMART_T_TIERS = {"core", "auxiliary"}


def smart_t_backtest_strategy_keys(db: Session) -> list[str]:
    """Resolve SmartT research scope from strategy metadata, not hardcoded keys."""

    response = StrategyMetadataService(db).list_strategy_meta()
    keys = [
        item.key
        for item in response.strategies
        if item.enabled
        and item.visibility != "backtest_only"
        and item.visibility != "hidden"
        and item.category_key in _SMART_T_TIERS
    ]
    return list(dict.fromkeys(keys))
