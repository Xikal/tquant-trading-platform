from __future__ import annotations


def is_etf(symbol: str) -> bool:
    return str(symbol).startswith(("15", "16", "51", "58"))


def is_fund_like(symbol: str, instrument_type: str = "") -> bool:
    normalized_type = str(instrument_type or "").strip().lower()
    if normalized_type in {"etf", "fund", "lof", "index_fund", "money_fund"}:
        return True
    return is_etf(symbol)


def a_share_price_limit_pct(
    symbol: str,
    *,
    instrument_type: str = "",
    market: str = "CN",
) -> float | None:
    normalized_market = str(market or "CN").strip().upper()
    if normalized_market not in {"CN", "A", "A_SHARE", "SH", "SZ", "BJ"}:
        return None
    if is_fund_like(symbol, instrument_type):
        return None
    normalized_type = str(instrument_type or "stock").strip().lower()
    if normalized_type not in {"stock", "equity", "a_share", "ashare"}:
        return None
    code = str(symbol or "").strip()
    if code.startswith(("688", "689", "300", "301")):
        return 20.0
    if code.startswith(("8", "4", "920")):
        return 30.0
    return 10.0
