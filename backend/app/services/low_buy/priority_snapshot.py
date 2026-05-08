from __future__ import annotations

from typing import Protocol

from app.models.schemas import LowBuyStrategyPerformanceOut
from app.repositories.low_buy.results import LowBuyResultRepository
from app.services.low_buy.priority_types import PriorityBaseSnapshot, PriorityCandidate
from app.services.low_buy.shared import PLAYBOOKS, Session
from app.services.low_buy.strategy_policy import StrategyTier
from app.services.low_buy.strategy_tier_resolver import StrategyTierResolver


class PrioritySnapshotBuilder(Protocol):
    def _resolve_priority_target_trade_date(self) -> str: ...

    def _load_watchlist_symbols(self, db: Session) -> set[str]: ...

    def _load_materialized_full_result(
        self,
        db: Session,
        strategy: str,
        latest_trade_date: str,
        limit: int,
        include_history: bool,
    ): ...

    def _collect_priority_candidates(
        self,
        db: Session,
        merged_candidates: dict[str, PriorityCandidate],
        tracked_symbols: set[str],
        latest_trade_date: str,
        candidates: list,
        performance_cache: dict[tuple[str, str, int], LowBuyStrategyPerformanceOut | None],
    ) -> None: ...

    def _build_market_context(self, db: Session, latest_trade_date: str): ...


def build_priority_base_snapshot(
    *,
    builder: PrioritySnapshotBuilder,
    db: Session,
    limit: int,
) -> PriorityBaseSnapshot:
    repository = LowBuyResultRepository(db)
    target_trade_date = builder._resolve_priority_target_trade_date()
    latest_result_trade_date = repository.fetch_latest_trade_date() or ""
    latest_available_trade_date = target_trade_date or latest_result_trade_date
    tracked_symbols = builder._load_watchlist_symbols(db)
    merged_candidates: dict[str, PriorityCandidate] = {}
    performance_cache: dict[tuple[str, str, int], LowBuyStrategyPerformanceOut | None] = {}
    latest_trade_date = ""
    updated_at = ""
    missing_strategies: list[str] = []
    stale_strategies: list[str] = []
    tier_resolver = StrategyTierResolver(db)

    for strategy_key in PLAYBOOKS:
        if tier_resolver.resolve(strategy_key) not in {StrategyTier.CORE, StrategyTier.AUXILIARY}:
            continue
        summary = (
            repository.fetch_latest_scan_summary_on_or_before(
                strategy_key=strategy_key,
                latest_trade_date=target_trade_date,
            )
            if target_trade_date
            else repository.fetch_latest_scan_summary(strategy_key=strategy_key)
        )
        if summary is None:
            missing_strategies.append(strategy_key)
            continue
        payload = builder._load_materialized_full_result(
            db=db,
            strategy=strategy_key,
            latest_trade_date=str(summary.latest_trade_date),
            limit=max(limit * 2, 24),
            include_history=False,
        )
        if payload is None:
            missing_strategies.append(strategy_key)
            continue
        if latest_available_trade_date and payload.latest_trade_date < latest_available_trade_date:
            stale_strategies.append(strategy_key)
        latest_trade_date = max(latest_trade_date, payload.latest_trade_date)
        updated_at = max(updated_at, payload.full_scan_updated_at or payload.as_of_date)
        builder._collect_priority_candidates(
            db=db,
            merged_candidates=merged_candidates,
            tracked_symbols=tracked_symbols,
            latest_trade_date=payload.latest_trade_date,
            candidates=payload.confirmed_candidates + payload.candidates,
            performance_cache=performance_cache,
        )

    market_context = builder._build_market_context(db=db, latest_trade_date=latest_trade_date)
    return PriorityBaseSnapshot(
        latest_trade_date=latest_trade_date,
        latest_available_trade_date=latest_available_trade_date,
        updated_at=updated_at,
        candidates=list(merged_candidates.values()),
        market_context=market_context,
        missing_strategies=missing_strategies,
        stale_strategies=stale_strategies,
    )
