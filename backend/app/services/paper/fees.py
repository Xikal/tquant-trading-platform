from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from app.services.paper.symbols import is_etf

STOCK_COMMISSION_RATE = Decimal("0.000085")
STOCK_MIN_COMMISSION = Decimal("5.00")
ETF_COMMISSION_RATE = Decimal("0.00005")
STOCK_STAMP_TAX_RATE = Decimal("0.0005")
STOCK_TRANSFER_FEE_RATE = Decimal("0.00001")
STOCK_TRANSFER_FEE_CAP = Decimal("500.00")
SHANGHAI_STOCK_PREFIXES = ("60", "68", "900")


@dataclass(frozen=True)
class FeeDetail:
    gross_amount: Decimal
    commission: Decimal
    stamp_tax: Decimal
    transfer_fee: Decimal
    total_fee: Decimal
    net_amount: Decimal


def calculate_fee(*, symbol: str, side: str, price: Decimal, quantity: int) -> FeeDetail:
    gross = _money(price * Decimal(quantity))
    etf = is_etf(symbol)
    commission = _commission(gross, etf=etf)
    stamp_tax = _money(gross * STOCK_STAMP_TAX_RATE) if side == "sell" and not etf else Decimal("0.00")
    transfer_fee = _transfer_fee(symbol=symbol, gross=gross, etf=etf)
    total = _money(commission + stamp_tax + transfer_fee)
    net = _money(gross + total) if side == "buy" else _money(gross - total)
    return FeeDetail(
        gross_amount=gross,
        commission=commission,
        stamp_tax=stamp_tax,
        transfer_fee=transfer_fee,
        total_fee=total,
        net_amount=net,
    )


def commission_warning_text(*, gross_amount: Decimal, total_fee: Decimal) -> str:
    if gross_amount <= 0:
        return ""
    fee_rate = total_fee / gross_amount
    if fee_rate >= Decimal("0.01"):
        return "手续费占比较高，单笔金额偏小，容易吞噬收益。"
    if fee_rate >= Decimal("0.005"):
        return "手续费占比偏高，建议合并小额委托。"
    return ""


def _commission(gross: Decimal, *, etf: bool) -> Decimal:
    if etf:
        return _money(gross * ETF_COMMISSION_RATE)
    return max(_money(gross * STOCK_COMMISSION_RATE), STOCK_MIN_COMMISSION)


def _transfer_fee(*, symbol: str, gross: Decimal, etf: bool) -> Decimal:
    if etf or not _is_shanghai_stock(symbol):
        return Decimal("0.00")
    return min(_money(gross * STOCK_TRANSFER_FEE_RATE), STOCK_TRANSFER_FEE_CAP)


def _is_shanghai_stock(symbol: str) -> bool:
    clean = str(symbol or "").strip()
    return clean.startswith(SHANGHAI_STOCK_PREFIXES)


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
