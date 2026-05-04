from __future__ import annotations

from typing import Protocol

from app.models.schemas import LowBuyCandidateOut, LowBuyStrategyPerformanceOut
from app.services.low_buy.priority_types import StrategyHit
from app.services.low_buy.shared import (
    PERFORMANCE_LOOKBACK_DAYS,
    RECENT_PERFORMANCE_LOOKBACK_DAYS,
    Session,
)
from app.services.low_buy.strategy_families import resolve_strategy_family


class PriorityPerformanceBuilder(Protocol):
    def _load_cached_strategy_performance(
        self,
        db: Session,
        strategy_key: str,
        latest_trade_date: str,
        cache: dict[tuple[str, str, int], LowBuyStrategyPerformanceOut | None],
        lookback_days: int,
        build_if_missing: bool,
    ) -> LowBuyStrategyPerformanceOut | None: ...

    def _strategy_weight_score(
        self,
        performance: LowBuyStrategyPerformanceOut | None,
        recent_performance: LowBuyStrategyPerformanceOut | None,
    ) -> float: ...

    def _strategy_context_bonus(
        self,
        candidate: LowBuyCandidateOut,
        performance: LowBuyStrategyPerformanceOut | None,
        recent_performance: LowBuyStrategyPerformanceOut | None,
    ) -> float: ...

    def _apply_priority_position_adjustment(
        self,
        candidate: LowBuyCandidateOut,
        performance: LowBuyStrategyPerformanceOut | None,
    ) -> LowBuyCandidateOut: ...


def build_strategy_hit(
    *,
    builder: PriorityPerformanceBuilder,
    db: Session,
    candidate: LowBuyCandidateOut,
    latest_trade_date: str,
    performance_cache: dict[tuple[str, str, int], LowBuyStrategyPerformanceOut | None],
) -> StrategyHit:
    base_performance = builder._load_cached_strategy_performance(
        db=db,
        strategy_key=candidate.strategy_key,
        latest_trade_date=latest_trade_date,
        cache=performance_cache,
        lookback_days=PERFORMANCE_LOOKBACK_DAYS,
        build_if_missing=False,
    )
    recent_performance = builder._load_cached_strategy_performance(
        db=db,
        strategy_key=candidate.strategy_key,
        latest_trade_date=latest_trade_date,
        cache=performance_cache,
        lookback_days=RECENT_PERFORMANCE_LOOKBACK_DAYS,
        build_if_missing=False,
    )
    strategy_weight_score = builder._strategy_weight_score(base_performance, recent_performance)
    context_bonus = builder._strategy_context_bonus(candidate, base_performance, recent_performance)
    adjusted_candidate = builder._apply_priority_position_adjustment(
        candidate,
        base_performance,
    )
    return StrategyHit(
        strategy_key=candidate.strategy_key,
        strategy_title=candidate.strategy_title,
        family_key=resolve_strategy_family(candidate.strategy_key),
        candidate=adjusted_candidate,
        strategy_weight_score=strategy_weight_score,
        context_bonus=context_bonus,
        performance=base_performance,
    )
