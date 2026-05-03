from __future__ import annotations


def is_etf(symbol: str) -> bool:
    return str(symbol).startswith(("15", "16", "51", "58"))
