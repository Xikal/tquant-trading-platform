from __future__ import annotations

from decimal import Decimal

from app.services.paper.fees import calculate_fee


def test_stock_commission_uses_085_per_ten_thousand_with_minimum() -> None:
    small = calculate_fee(symbol="600000", side="buy", price=Decimal("10.00"), quantity=100)
    large = calculate_fee(symbol="600000", side="buy", price=Decimal("10.00"), quantity=10_000)

    assert small.gross_amount == Decimal("1000.00")
    assert small.commission == Decimal("5.00")
    assert large.gross_amount == Decimal("100000.00")
    assert large.commission == Decimal("8.50")


def test_stock_sell_keeps_stamp_tax_and_transfer_fee() -> None:
    fee = calculate_fee(symbol="600000", side="sell", price=Decimal("10.00"), quantity=10_000)

    assert fee.commission == Decimal("8.50")
    assert fee.stamp_tax == Decimal("50.00")
    assert fee.transfer_fee == Decimal("1.00")
    assert fee.total_fee == Decimal("59.50")


def test_shenzhen_stock_has_no_transfer_fee() -> None:
    fee = calculate_fee(symbol="000001", side="sell", price=Decimal("10.00"), quantity=10_000)

    assert fee.commission == Decimal("8.50")
    assert fee.stamp_tax == Decimal("50.00")
    assert fee.transfer_fee == Decimal("0.00")
    assert fee.total_fee == Decimal("58.50")


def test_shanghai_transfer_fee_is_capped() -> None:
    fee = calculate_fee(symbol="600000", side="buy", price=Decimal("100.00"), quantity=1_000_000)

    assert fee.transfer_fee == Decimal("500.00")


def test_etf_commission_uses_05_per_ten_thousand_without_stock_minimum() -> None:
    fee = calculate_fee(symbol="510300", side="buy", price=Decimal("4.00"), quantity=1_000)

    assert fee.gross_amount == Decimal("4000.00")
    assert fee.commission == Decimal("0.20")
    assert fee.stamp_tax == Decimal("0.00")
    assert fee.transfer_fee == Decimal("0.00")
