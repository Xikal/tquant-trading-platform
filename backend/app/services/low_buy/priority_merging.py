from __future__ import annotations

from typing import Protocol

from app.models.schemas import LowBuyCandidateOut, LowBuyStrategyPerformanceOut
from app.services.low_buy.priority_family import recommendation_days_by_title
from app.services.low_buy.priority_types import PriorityCandidate, StrategyHit
from app.services.low_buy.recommendation_duration import attach_recommendation_durations
from app.services.low_buy.shared import Session


class PriorityMergeBuilder(Protocol):
    def _build_strategy_hit(
        self,
        db: Session,
        candidate: LowBuyCandidateOut,
        latest_trade_date: str,
        performance_cache: dict[tuple[str, str, int], LowBuyStrategyPerformanceOut | None],
    ) -> StrategyHit: ...

    def _single_strategy_rank(self, candidate: LowBuyCandidateOut, strategy_weight: float) -> float: ...

    def _ordered_hits_for_aggregation(self, hits: list[StrategyHit]) -> list[StrategyHit]: ...


def collect_priority_candidates(
    *,
    builder: PriorityMergeBuilder,
    db: Session,
    merged_candidates: dict[str, PriorityCandidate],
    tracked_symbols: set[str],
    latest_trade_date: str,
    candidates: list[LowBuyCandidateOut],
    performance_cache: dict[tuple[str, str, int], LowBuyStrategyPerformanceOut | None],
) -> None:
    for candidate in candidates:
        if candidate.symbol in tracked_symbols or candidate.buy_signal_state == "avoid":
            continue
        strategy_key = candidate.strategy_key
        row = merged_candidates.setdefault(candidate.symbol, PriorityCandidate(symbol=candidate.symbol))
        hit = builder._build_strategy_hit(
            db=db,
            candidate=candidate,
            latest_trade_date=latest_trade_date,
            performance_cache=performance_cache,
        )
        upsert_strategy_hit(builder=builder, row=row, hit=hit, strategy_key=strategy_key)


def upsert_strategy_hit(
    *,
    builder: PriorityMergeBuilder,
    row: PriorityCandidate,
    hit: StrategyHit,
    strategy_key: str,
) -> None:
    for index, existing in enumerate(row.hits):
        if existing.strategy_key != strategy_key:
            continue
        if builder._single_strategy_rank(
            hit.candidate,
            hit.strategy_weight_score + hit.context_bonus,
        ) > builder._single_strategy_rank(
            existing.candidate,
            existing.strategy_weight_score + existing.context_bonus,
        ):
            row.hits[index] = hit
        return
    row.hits.append(hit)


def attach_priority_recommendation_durations(
    *,
    db: Session,
    rows: list[PriorityCandidate],
    latest_trade_date: str,
) -> list[PriorityCandidate]:
    candidates = [hit.candidate for row in rows for hit in row.hits]
    enriched = attach_recommendation_durations(
        db=db,
        candidates=candidates,
        latest_trade_date=latest_trade_date,
    )
    enriched_by_key = {(candidate.strategy_key, candidate.symbol): candidate for candidate in enriched}
    result: list[PriorityCandidate] = []
    for row in rows:
        result.append(
            PriorityCandidate(
                symbol=row.symbol,
                hits=[
                    StrategyHit(
                        strategy_key=hit.strategy_key,
                        strategy_title=hit.strategy_title,
                        family_key=hit.family_key,
                        candidate=enriched_by_key.get((hit.strategy_key, hit.candidate.symbol), hit.candidate),
                        strategy_weight_score=hit.strategy_weight_score,
                        context_bonus=hit.context_bonus,
                        performance=hit.performance,
                    )
                    for hit in row.hits
                ],
            )
        )
    return result


def display_strategy_titles(
    *,
    builder: PriorityMergeBuilder,
    hits: list[StrategyHit],
) -> list[str]:
    titles_by_family: dict[str, str] = {}
    for hit in builder._ordered_hits_for_aggregation(hits):
        family_key = hit.family_key or hit.strategy_key
        if family_key in titles_by_family:
            continue
        titles_by_family[family_key] = hit.strategy_title
    return list(titles_by_family.values())


def recommendation_days_by_hit_title(hits: list[StrategyHit]) -> dict[str, int]:
    return recommendation_days_by_title(hits)
