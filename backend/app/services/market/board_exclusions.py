from __future__ import annotations

import re

GROWTH_BOARD_STOCK_PREFIXES = ("300", "301", "688", "689")
GROWTH_BOARD_REJECT_REASON = "创业板/科创板股票已按当前规则剔除。"


def normalize_a_share_symbol(symbol: str) -> str:
    """Return the first 6-digit A-share code from common symbol formats."""

    value = str(symbol or "").strip().upper()
    match = re.search(r"(\d{6})", value)
    return match.group(1) if match else value


def is_growth_board_stock(symbol: str) -> bool:
    """True for ChiNext/STAR Market stock codes, excluding ETF-style prefixes."""

    code = normalize_a_share_symbol(symbol)
    return code.startswith(GROWTH_BOARD_STOCK_PREFIXES)
