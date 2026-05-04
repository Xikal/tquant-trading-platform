from __future__ import annotations

from typing import Protocol

from app.models.schemas import LowBuyCandidateOut, LowBuyPortfolioRiskOut
from app.repositories.low_buy.lifecycle import LowBuyTradeLifecycleRepository
from app.services.low_buy.portfolio_risk import build_lifecycle_holdings, build_portfolio_risk
from app.services.low_buy.priority_types import PriorityCandidate, PriorityMarketContext, StrategyHit
from app.services.low_buy.shared import Session


class PriorityPortfolioSelector(Protocol):
    def _aggregate_strategy_weight(self, hits: list[StrategyHit]) -> float: ...

    def _effective_family_count(self, hits: list[StrategyHit]) -> int: ...

    def _final_rank_score(
        self,
        candidate: LowBuyCandidateOut,
        aggregate_weight: float,
        family_count: int,
        strategy_weight: float,
        market_context: PriorityMarketContext,
    ) -> float: ...


def build_priority_portfolio_risk(
    *,
    db: Session,
    rows: list[PriorityCandidate],
    market_context: PriorityMarketContext,
    selector: PriorityPortfolioSelector,
) -> LowBuyPortfolioRiskOut:
    portfolio_candidates = select_primary_candidates_for_portfolio(
        rows=rows,
        market_context=market_context,
        selector=selector,
    )
    active_holdings = build_lifecycle_holdings(
        LowBuyTradeLifecycleRepository(db).fetch_active(limit=300)
    )
    return build_portfolio_risk(
        portfolio_candidates,
        market_state=market_context.market_state,
        active_holdings=active_holdings,
    )


def select_primary_candidates_for_portfolio(
    *,
    rows: list[PriorityCandidate],
    market_context: PriorityMarketContext,
    selector: PriorityPortfolioSelector,
) -> list[LowBuyCandidateOut]:
    candidates: list[LowBuyCandidateOut] = []
    for row in rows:
        if not row.hits:
            continue
        aggregate_weight = selector._aggregate_strategy_weight(row.hits)
        family_count = selector._effective_family_count(row.hits)
        primary_hit = max(
            row.hits,
            key=lambda hit: selector._final_rank_score(
                candidate=hit.candidate,
                aggregate_weight=aggregate_weight,
                family_count=family_count,
                strategy_weight=hit.strategy_weight_score + hit.context_bonus,
                market_context=market_context,
            ),
        )
        candidates.append(primary_hit.candidate)
    return candidates
