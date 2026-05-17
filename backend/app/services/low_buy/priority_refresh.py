from __future__ import annotations

from typing import Protocol

from app.models.schemas import LowBuyCandidateOut
from app.services.low_buy.priority_types import PriorityCandidate, StrategyHit
from app.services.low_buy.shared import Any

PRIORITY_INTRADAY_CONFIRMATION_LIMIT = 12


class PriorityRefreshBuilder(Protocol):
    market_data: Any

    def _refresh_buy_signal(
        self,
        candidate: LowBuyCandidateOut,
        quote: Any | None = None,
        intraday_bars: list[Any] | None = None,
        require_intraday_structure: bool = False,
    ) -> LowBuyCandidateOut: ...

    def _distance_to_entry_zone_pct(self, candidate: LowBuyCandidateOut, latest_price: float) -> float: ...


def refresh_priority_candidates(
    *,
    builder: PriorityRefreshBuilder,
    rows: list[PriorityCandidate],
) -> list[PriorityCandidate]:
    symbols = [row.symbol for row in rows]
    quote_map = builder.market_data.get_quotes_batch(
        symbols,
        force_refresh=False,
        allow_slow_fallback=False,
    )
    intraday_bars_by_symbol = load_priority_intraday_bars(
        builder=builder,
        rows=rows,
        quote_map=quote_map,
    )
    refreshed_rows: list[PriorityCandidate] = []
    for row in rows:
        quote = quote_map.get(row.symbol)
        if not quote:
            refreshed_rows.append(row)
            continue
        refreshed_hits = [
            StrategyHit(
                strategy_key=hit.strategy_key,
                strategy_title=hit.strategy_title,
                family_key=hit.family_key,
                candidate=builder._refresh_buy_signal(
                    hit.candidate,
                    quote=quote,
                    intraday_bars=intraday_bars_by_symbol.get(row.symbol),
                    require_intraday_structure=True,
                ),
                strategy_weight_score=hit.strategy_weight_score,
                context_bonus=hit.context_bonus,
                performance=hit.performance,
            )
            for hit in row.hits
        ]
        refreshed_rows.append(PriorityCandidate(symbol=row.symbol, hits=refreshed_hits))
    return refreshed_rows


def load_priority_intraday_bars(
    *,
    builder: PriorityRefreshBuilder,
    rows: list[PriorityCandidate],
    quote_map: dict[str, object],
    max_symbols: int = PRIORITY_INTRADAY_CONFIRMATION_LIMIT,
) -> dict[str, list]:
    ranked_symbols: list[tuple[tuple[int, float, float], str]] = []
    for row in rows:
        quote = quote_map.get(row.symbol)
        if quote is None or not priority_needs_intraday_confirmation(row, quote):
            continue
        ranked_symbols.append((priority_intraday_rank(builder=builder, row=row, quote=quote), row.symbol))
    ranked_symbols.sort()
    effective_limit = min(max_symbols, PRIORITY_INTRADAY_CONFIRMATION_LIMIT)
    eligible_symbols = [symbol for _, symbol in ranked_symbols[:effective_limit]]
    return builder.market_data.get_intraday_bars_batch(
        symbols=eligible_symbols,
        period="1m",
        limit=30,
        max_workers=8,
        allow_slow_fallback=False,
    )


def priority_needs_intraday_confirmation(row: PriorityCandidate, quote: object) -> bool:
    latest_price = float(getattr(quote, "last_price", 0.0) or 0.0)
    if latest_price <= 0:
        return False
    for hit in row.hits:
        candidate = hit.candidate
        if latest_price <= candidate.stop_loss * 1.003:
            continue
        if latest_price <= candidate.entry_zone_high * 1.012:
            return True
    return False


def priority_intraday_rank(
    *,
    builder: PriorityRefreshBuilder,
    row: PriorityCandidate,
    quote: object,
) -> tuple[int, float, float]:
    latest_price = float(getattr(quote, "last_price", 0.0) or 0.0)
    best_state_rank = 9
    best_distance = 99.0
    best_score = 0.0
    state_rank = {"buy_now": 0, "soft_buy_now": 1, "observe_confirmed": 2, "near_entry": 3, "watch": 4}
    for hit in row.hits:
        candidate = hit.candidate
        best_state_rank = min(best_state_rank, state_rank.get(candidate.buy_signal_state, 5))
        distance = builder._distance_to_entry_zone_pct(candidate, latest_price)
        best_distance = min(best_distance, distance)
        best_score = max(best_score, float(candidate.score or 0.0))
    return (best_state_rank, best_distance, -best_score)
