from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from app.models.schemas import LowBuyCandidateOut, LowBuyScreenerResponse
from app.repositories.low_buy.results import LowBuyResultRepository
from app.services.low_buy.shared import Session

ACTIONABLE_SIGNAL_STATES = frozenset({"buy_now", "soft_buy_now", "observe_confirmed", "near_entry"})
RECOMMENDATION_LOOKBACK_DAYS = 80


@dataclass(frozen=True)
class RecommendationDuration:
    start_date: str | None
    days: int


def attach_recommendation_durations(
    *,
    db: Session,
    candidates: list[LowBuyCandidateOut],
    latest_trade_date: str,
    lookback_days: int = RECOMMENDATION_LOOKBACK_DAYS,
) -> list[LowBuyCandidateOut]:
    if not candidates or not latest_trade_date:
        return [candidate.model_copy(deep=True) for candidate in candidates]

    durations = _load_recommendation_durations(
        db=db,
        candidates=candidates,
        latest_trade_date=latest_trade_date,
        lookback_days=lookback_days,
    )
    enriched: list[LowBuyCandidateOut] = []
    for candidate in candidates:
        duration = durations.get((candidate.strategy_key, candidate.symbol), RecommendationDuration(None, 0))
        strategy_days = {candidate.strategy_title: duration.days} if duration.days > 0 else {}
        enriched.append(
            candidate.model_copy(
                update={
                    "recommendation_start_date": duration.start_date,
                    "recommendation_days": duration.days,
                    "strategy_recommendation_days": strategy_days,
                    "recommendation_duration_text": _duration_text(candidate, duration),
                }
            )
        )
    return enriched


def attach_response_recommendation_durations(
    *,
    db: Session,
    payload: LowBuyScreenerResponse,
) -> LowBuyScreenerResponse:
    current_candidates = attach_recommendation_durations(
        db=db,
        candidates=payload.confirmed_candidates + payload.candidates,
        latest_trade_date=payload.latest_trade_date,
    )
    by_key = {(candidate.strategy_key, candidate.symbol): candidate for candidate in current_candidates}
    return payload.model_copy(
        update={
            "confirmed_candidates": [
                by_key.get((candidate.strategy_key, candidate.symbol), candidate)
                for candidate in payload.confirmed_candidates
            ],
            "candidates": [
                by_key.get((candidate.strategy_key, candidate.symbol), candidate)
                for candidate in payload.candidates
            ],
        }
    )


def _load_recommendation_durations(
    *,
    db: Session,
    candidates: list[LowBuyCandidateOut],
    latest_trade_date: str,
    lookback_days: int,
) -> dict[tuple[str, str], RecommendationDuration]:
    actionable = [candidate for candidate in candidates if candidate.buy_signal_state in ACTIONABLE_SIGNAL_STATES]
    if not actionable:
        return {}

    repository = LowBuyResultRepository(db)
    candidates_by_strategy: dict[str, list[LowBuyCandidateOut]] = defaultdict(list)
    for candidate in actionable:
        candidates_by_strategy[candidate.strategy_key].append(candidate)

    durations: dict[tuple[str, str], RecommendationDuration] = {}
    for strategy_key, strategy_candidates in candidates_by_strategy.items():
        symbols = sorted({candidate.symbol for candidate in strategy_candidates})
        recent_dates = _recent_trade_dates(
            repository=repository,
            strategy_key=strategy_key,
            latest_trade_date=latest_trade_date,
            lookback_days=lookback_days,
        )
        historical_dates = [date for date in recent_dates if date != latest_trade_date]
        rows = repository.fetch_results_for_symbols_on_dates(
            strategy_key=strategy_key,
            latest_trade_dates=historical_dates,
            symbols=symbols,
            signal_states=tuple(ACTIONABLE_SIGNAL_STATES),
        )
        actionable_pairs = {(row.latest_trade_date, row.symbol) for row in rows}
        for candidate in strategy_candidates:
            durations[(strategy_key, candidate.symbol)] = _count_consecutive_days(
                symbol=candidate.symbol,
                latest_trade_date=latest_trade_date,
                historical_dates=historical_dates,
                actionable_pairs=actionable_pairs,
            )
    return durations


def _recent_trade_dates(
    *,
    repository: LowBuyResultRepository,
    strategy_key: str,
    latest_trade_date: str,
    lookback_days: int,
) -> list[str]:
    dates = [latest_trade_date]
    for summary in repository.fetch_recent_scan_summaries(strategy_key=strategy_key, limit=lookback_days):
        trade_date = str(summary.latest_trade_date)
        if trade_date <= latest_trade_date and trade_date not in dates:
            dates.append(trade_date)
    return sorted(dates, reverse=True)


def _count_consecutive_days(
    *,
    symbol: str,
    latest_trade_date: str,
    historical_dates: list[str],
    actionable_pairs: set[tuple[str, str]],
) -> RecommendationDuration:
    days = 1
    start_date = latest_trade_date
    for trade_date in historical_dates:
        if (trade_date, symbol) not in actionable_pairs:
            break
        days += 1
        start_date = trade_date
    return RecommendationDuration(start_date=start_date, days=days)


def _duration_text(candidate: LowBuyCandidateOut, duration: RecommendationDuration) -> str:
    if duration.days <= 0:
        return ""
    max_holding_days = max(int(candidate.exit_plan.max_holding_days or 0), 1)
    if duration.days >= max_holding_days:
        return f"{candidate.strategy_title}第 {duration.days} 天，已达到建议验证窗口 {max_holding_days} 天；未转强应降级或退出。"
    remaining = max_holding_days - duration.days
    return f"{candidate.strategy_title}第 {duration.days} 天，建议验证窗口 {max_holding_days} 天；剩余 {remaining} 天。"
