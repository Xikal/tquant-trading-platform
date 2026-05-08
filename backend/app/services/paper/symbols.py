from __future__ import annotations


def is_etf(symbol: str) -> bool:
    return str(symbol).startswith(("15", "16", "51", "58"))


def is_fund_like(symbol: str, instrument_type: str = "") -> bool:
    normalized_type = str(instrument_type or "").strip().lower()
    if normalized_type in {"etf", "fund", "lof", "index_fund", "money_fund"}:
        return True
    return is_etf(symbol)


def price_tick(symbol: str, instrument_type: str = "") -> str:
    """Return the minimum quoted price increment used by the paper matcher.

    A 股股票通常按 0.01 元报价；ETF/基金类常见报价精度为 0.001 元。
    这里用于模拟成交价量化，不改变外部行情原始价格。
    """

    return "0.001" if is_fund_like(symbol, instrument_type) else "0.01"


def a_share_price_limit_pct(
    symbol: str,
    *,
    instrument_type: str = "",
    market: str = "CN",
    is_st: bool = False,
    listing_days: int | None = None,
    limit_exempt: bool = False,
) -> float | None:
    normalized_market = str(market or "CN").strip().upper()
    if normalized_market not in {"CN", "A", "A_SHARE", "SH", "SZ", "BJ"}:
        return None
    if is_fund_like(symbol, instrument_type):
        return None
    if limit_exempt:
        return None
    if is_st:
        return 5.0
    if listing_days is not None and listing_days <= 5:
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
