from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from app.services.paper.symbols import is_etf


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
    commission = max(_money(gross * Decimal("0.00025")), Decimal("5.00"))
    stamp_tax = _money(gross * Decimal("0.0005")) if side == "sell" and not is_etf(symbol) else Decimal("0.00")
    transfer_fee = Decimal("0.00") if is_etf(symbol) else _money(gross * Decimal("0.00001"))
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


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
