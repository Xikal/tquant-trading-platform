from __future__ import annotations

from dataclasses import replace
from typing import Any

from sqlalchemy.orm import Session

from app.services.paper.portfolio_allocator import PaperStrategyPortfolioAllocator


def apply_portfolio_weighting(
    *,
    db: Session,
    account_id: int,
    candidates: list[Any],
) -> list[Any]:
    decisions = PaperStrategyPortfolioAllocator(db).build_strategy_scales(account_id=account_id)
    if not decisions:
        return candidates
    weighted = []
    for candidate in candidates:
        strategy_key = str(candidate.signal.get("strategy_key") or "")
        decision = decisions.get(strategy_key)
        if decision is None:
            weighted.append(candidate)
            continue
        signal = dict(candidate.signal)
        signal["portfolio_weight_scale"] = float(decision.scale)
        signal["portfolio_weight_pct"] = round(decision.weight * 100, 2)
        signal["portfolio_weight_reason"] = decision.reason
        signal["portfolio_max_correlation"] = decision.max_correlation
        weighted.append(replace(candidate, signal=signal))
    return weighted
