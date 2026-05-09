from __future__ import annotations

from collections.abc import Callable

from app.services.market.regime_types import STYLE_PROXY_GROUPS


def load_style_proxy_changes(get_quotes_batch: Callable[[list[str]], dict]) -> tuple[float, float]:
    symbols = list({symbol for values in STYLE_PROXY_GROUPS.values() for symbol in values})
    quote_map = get_quotes_batch(symbols)
    return (
        average_quote_change(quote_map, STYLE_PROXY_GROUPS["large"]),
        average_quote_change(quote_map, STYLE_PROXY_GROUPS["small"]),
    )


def average_quote_change(quote_map, symbols: tuple[str, ...]) -> float:
    values = [
        float(getattr(quote_map.get(symbol), "change_pct", 0.0) or 0.0)
        for symbol in symbols
        if quote_map.get(symbol) is not None
    ]
    if not values:
        return 0.0
    return round(sum(values) / len(values), 4)
