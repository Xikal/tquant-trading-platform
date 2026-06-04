from __future__ import annotations

from decimal import Decimal

from app.services.execution_model.rules import available_quantity_for_date, lot_sized_quantity, position_return_pct, weighted_cost_basis


def test_execution_model_position_rules_keep_t_plus_one_and_lot_semantics() -> None:
    assert lot_sized_quantity(299) == 200
    assert lot_sized_quantity(300) == 300
    assert available_quantity_for_date([(100, "2026-06-05"), (200, "2026-06-06")], trade_date="2026-06-05", symbol="600000") == 100
    assert available_quantity_for_date([(100, "2026-06-05")], trade_date="2026-06-04", symbol="600000") == 0


def test_execution_model_exit_rules_match_existing_return_math() -> None:
    assert weighted_cost_basis(Decimal("10.00"), 100, Decimal("12.00"), 100) == Decimal("11.0000")
    assert round(position_return_pct(entry_price=Decimal("10.00"), exit_price=Decimal("10.80")), 2) == 8.0
    assert position_return_pct(entry_price=Decimal("0"), exit_price=Decimal("10.80")) == 0.0
