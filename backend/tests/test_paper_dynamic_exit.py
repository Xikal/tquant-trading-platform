from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from app.services.paper.dynamic_exit import evaluate_paper_exit


def _position(**overrides):
    values = {
        "available_quantity": 1000,
        "cost_basis": 10.0,
        "opened_at": datetime(2026, 5, 8, 10, 0, 0),
        "strategy_sources": '["first_board"]',
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_dynamic_exit_stops_loss_full_position() -> None:
    decision = evaluate_paper_exit(_position(), price=9.6, now=datetime(2026, 5, 9, 10, 0, 0))

    assert decision.quantity == 1000
    assert decision.code == "hard_stop_loss"
    assert "动态止损" in decision.reason


def test_dynamic_exit_protects_profit_after_one_day() -> None:
    decision = evaluate_paper_exit(_position(), price=10.35, now=datetime(2026, 5, 9, 10, 0, 0))

    assert decision.quantity == 500
    assert decision.code == "profit_protection"
    assert "利润保护" in decision.reason


def test_dynamic_exit_keeps_small_profit_to_avoid_washout() -> None:
    decision = evaluate_paper_exit(_position(), price=10.15, now=datetime(2026, 5, 9, 10, 0, 0))

    assert decision.quantity == 0
    assert decision.code == "hold"


def test_dynamic_exit_strong_profit_locks_all() -> None:
    decision = evaluate_paper_exit(_position(), price=10.9, now=datetime(2026, 5, 9, 10, 0, 0))

    assert decision.quantity == 1000
    assert decision.code == "strong_take_profit"


def test_sector_etf_t0_uses_shorter_exit_threshold() -> None:
    row = _position(strategy_sources='["sector_etf_t0"]', opened_at=datetime(2026, 5, 9, 9, 40, 0))
    decision = evaluate_paper_exit(row, price=10.13, now=datetime(2026, 5, 9, 10, 0, 0))

    assert decision.quantity == 1000
    assert decision.code == "etf_take_profit"


def test_dynamic_exit_time_rule_uses_holding_policy_window() -> None:
    row = _position(opened_at=datetime(2026, 5, 1, 10, 0, 0))
    decision = evaluate_paper_exit(row, price=10.1, now=datetime(2026, 5, 8, 10, 0, 0))

    assert decision.quantity == 1000
    assert decision.code == "time_exit"
