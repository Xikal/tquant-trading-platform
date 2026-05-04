from __future__ import annotations

from typing import Protocol

from app.services.low_buy.shared import Any, LowBuyCandidateOut


class LiveQuoteSignalBuilder(Protocol):
    market_data: Any

    def _entry_position(self, candidate: LowBuyCandidateOut, latest_price: float) -> str: ...

    def _refresh_buy_signal(
        self,
        candidate: LowBuyCandidateOut,
        quote: Any | None = None,
        intraday_bars: list[Any] | None = None,
        require_intraday_structure: bool = False,
    ) -> LowBuyCandidateOut: ...


def apply_live_quotes(
    *,
    builder: LiveQuoteSignalBuilder,
    candidates: list[LowBuyCandidateOut],
    quote_map: dict[str, Any] | None = None,
) -> list[LowBuyCandidateOut]:
    if not candidates:
        return []
    enriched_by_symbol: dict[str, LowBuyCandidateOut] = {}
    batch_quotes = quote_map or builder.market_data.get_quotes_batch([candidate.symbol for candidate in candidates])
    intraday_bars_by_symbol = load_live_quote_intraday_bars(
        builder=builder,
        candidates=candidates,
        quote_map=batch_quotes,
    )
    for candidate in candidates:
        quote = batch_quotes.get(candidate.symbol)
        if quote is None:
            enriched_by_symbol[candidate.symbol] = candidate
            continue
        refreshed = candidate.model_copy(
            update={
                "latest_price": round(float(quote.last_price), 3),
                "change_pct": round(float(quote.change_pct), 3),
                "quote_timestamp": str(quote.timestamp),
            }
        )
        enriched_by_symbol[candidate.symbol] = builder._refresh_buy_signal(
            refreshed,
            quote=quote,
            intraday_bars=intraday_bars_by_symbol.get(candidate.symbol),
            require_intraday_structure=True,
        )
    return [enriched_by_symbol.get(candidate.symbol, candidate) for candidate in candidates]


def load_live_quote_intraday_bars(
    *,
    builder: LiveQuoteSignalBuilder,
    candidates: list[LowBuyCandidateOut],
    quote_map: dict[str, Any],
    max_symbols: int = 24,
) -> dict[str, list[Any]]:
    symbols: list[str] = []
    for candidate in candidates:
        quote = quote_map.get(candidate.symbol)
        if quote is None:
            continue
        latest_price = float(getattr(quote, "last_price", 0.0) or 0.0)
        if latest_price <= 0:
            continue
        entry_position = builder._entry_position(candidate, latest_price)
        if entry_position not in {"in_zone", "below_zone", "near_above_zone"}:
            continue
        symbols.append(candidate.symbol)
        if len(symbols) >= max_symbols:
            break
    return builder.market_data.get_intraday_bars_batch(
        symbols=symbols,
        period="1m",
        limit=30,
        max_workers=8,
    )
