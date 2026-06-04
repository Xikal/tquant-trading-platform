from __future__ import annotations

from decimal import Decimal

from app.services.execution_model.events import (
    ExecutionFill,
    ExecutionOrder,
    ExecutionPosition,
    ExecutionSignal,
    ExitEvent,
)
from app.services.execution_model.recommendations import recommend_strategy_action
from app.services.execution_model.rules import (
    available_quantity_for_date,
    lot_sized_quantity,
    position_return_pct,
    weighted_cost_basis,
)


def test_execution_events_share_signal_order_fill_position_exit_shape() -> None:
    signal = ExecutionSignal(symbol="600000", trade_date="2026-06-04", strategy_key="first_board")
    order = ExecutionOrder(symbol="600000", trade_date="2026-06-04", strategy_key="first_board", quantity=200)
    fill = ExecutionFill(
        symbol="600000",
        trade_date="2026-06-04",
        strategy_key="first_board",
        quantity=200,
        fill_price=Decimal("10.02"),
    )
    position = ExecutionPosition(
        symbol="600000",
        trade_date="2026-06-04",
        strategy_key="first_board",
        quantity=200,
        available_quantity=0,
        cost_basis=Decimal("10.02"),
    )
    exit_event = ExitEvent(
        symbol="600000",
        trade_date="2026-06-05",
        strategy_key="first_board",
        quantity=200,
        exit_price=Decimal("10.50"),
        exit_reason="take_profit",
    )

    assert signal.as_payload()["kind"] == "signal"
    assert order.as_payload()["kind"] == "order"
    assert fill.as_payload()["kind"] == "fill"
    assert position.as_payload()["kind"] == "position"
    assert exit_event.as_payload()["kind"] == "exit"


def test_shared_execution_rules_match_paper_and_backtest_lot_semantics() -> None:
    assert weighted_cost_basis(Decimal("10"), 100, Decimal("12"), 100) == Decimal("11.0000")
    assert lot_sized_quantity(255) == 200
    assert available_quantity_for_date([(100, "2026-06-05"), (200, "2026-06-06")], trade_date="2026-06-05") == 100
    assert round(position_return_pct(entry_price=Decimal("10"), exit_price=Decimal("10.50")), 2) == 5.0


def test_strategy_recommendation_outputs_required_actions() -> None:
    retain = recommend_strategy_action(
        {
            "strategy_key": "first_board",
            "filled_count": 120,
            "profit_factor": 1.4,
            "avg_trade_return_pct": 0.35,
            "max_drawdown_pct": -20,
            "max5_portfolio_return_pct": 4.2,
            "max10_portfolio_return_pct": 5.8,
        }
    )
    downgrade = recommend_strategy_action(
        {
            "strategy_key": "first_board",
            "filled_count": 120,
            "profit_factor": 1.4,
            "avg_trade_return_pct": 0.35,
            "max_drawdown_pct": -20,
            "max5_portfolio_return_pct": -1.0,
            "max10_portfolio_return_pct": 5.8,
        }
    )
    default_off = recommend_strategy_action(
        {
            "strategy_key": "first_board",
            "filled_count": 20,
            "profit_factor": 1.4,
            "avg_trade_return_pct": 0.35,
            "max_drawdown_pct": -20,
            "max5_portfolio_return_pct": 4.2,
            "max10_portfolio_return_pct": 5.8,
        }
    )
    delete = recommend_strategy_action(
        {
            "strategy_key": "n_pattern_short_wash",
            "filled_count": 120,
            "profit_factor": 0.8,
            "avg_trade_return_pct": -0.2,
            "max_drawdown_pct": -20,
            "max5_portfolio_return_pct": 4.2,
            "max10_portfolio_return_pct": 5.8,
        }
    )

    assert retain.action == "retain"
    assert downgrade.action == "downgrade"
    assert default_off.action == "default_off"
    assert delete.action == "delete_candidate"
