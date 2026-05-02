from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP


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
    stamp_tax = _money(gross * Decimal("0.0005")) if side == "sell" and not _is_etf(symbol) else Decimal("0.00")
    transfer_fee = Decimal("0.00") if _is_etf(symbol) else _money(gross * Decimal("0.00001"))
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


def _is_etf(symbol: str) -> bool:
    return symbol.startswith(("15", "16", "51", "58"))


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

