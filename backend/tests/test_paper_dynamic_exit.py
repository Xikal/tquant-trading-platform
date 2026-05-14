from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from app.services.paper.dynamic_exit import evaluate_paper_exit
from app.services.paper.smart_exit_context import PaperExitContext


def _position(**overrides):
    values = {
        "available_quantity": 1000,
        "cost_basis": 10.0,
        "opened_at": datetime(2026, 5, 8, 10, 0, 0),
        "strategy_sources": '["first_board"]',
        "symbol": "600000",
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


def test_dynamic_exit_sells_no_volume_rally_in_batches() -> None:
    context = PaperExitContext(
        intraday_usable=True,
        above_vwap=False,
        volume_release_ratio=0.55,
        volume_usable=True,
        high_pullback_ratio=0.5,
        high_pullback_pct=1.2,
        reason="冲高回落且量能不足。",
    )
    decision = evaluate_paper_exit(
        _position(),
        price=10.25,
        now=datetime(2026, 5, 9, 10, 0, 0),
        context=context,
    )

    assert decision.quantity == 300
    assert decision.code == "no_volume_take_profit"
    assert decision.action_signal == "scale_out"
    assert "冲高无量" in decision.action_text


def test_dynamic_exit_holds_probable_wash_pullback() -> None:
    context = PaperExitContext(
        intraday_usable=True,
        reclaimed_vwap=True,
        low_rising=True,
        volume_release_ratio=0.5,
        volume_usable=True,
        reason="缩量回踩后重新站回分时均价线。",
    )
    decision = evaluate_paper_exit(
        _position(),
        price=9.82,
        now=datetime(2026, 5, 9, 10, 0, 0),
        context=context,
    )

    assert decision.quantity == 0
    assert decision.code == "hold"
    assert decision.action_signal == "washout"
    assert "疑似洗盘" in decision.action_text


def test_dynamic_exit_does_not_treat_unusable_volume_as_washout() -> None:
    context = PaperExitContext(
        intraday_usable=True,
        reclaimed_vwap=True,
        low_rising=True,
        volume_release_ratio=0.0,
        volume_usable=False,
        reason="分时量能样本不足。",
    )
    decision = evaluate_paper_exit(
        _position(),
        price=9.82,
        now=datetime(2026, 5, 9, 10, 0, 0),
        context=context,
    )

    assert decision.action_signal != "washout"
