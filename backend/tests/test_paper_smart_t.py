from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from app.services.paper.quote_quality import PaperQuotePrice
from app.services.paper.smart_exit_context import PaperExitContext
from app.services.paper.smart_t import build_smart_t_add_orders


def _account(**overrides):
    values = {
        "cash_available": 50000.0,
        "initial_cash": 100000.0,
        "total_assets": 100000.0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _position(**overrides):
    values = {
        "symbol": "600000",
        "name": "浦发银行",
        "available_quantity": 1000,
        "cost_basis": 10.0,
        "market_value": 10000.0,
        "opened_at": datetime(2026, 5, 8, 10, 0, 0),
        "strategy_sources": '["first_board"]',
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _quote(price: float = 9.86) -> PaperQuotePrice:
    return PaperQuotePrice(symbol="600000", price=price, quality="fresh", prev_close=10.0)


def _context() -> PaperExitContext:
    return PaperExitContext(
        intraday_usable=True,
        reclaimed_vwap=True,
        low_rising=True,
        volume_release_ratio=0.35,
        volume_usable=True,
        vwap=9.90,
        reason="缩量回踩后重新站回分时均价线。",
    )


def test_smart_t_add_order_created_for_wash_pullback() -> None:
    orders = build_smart_t_add_orders(
        account=_account(),
        positions=[_position()],
        prices={"600000": _quote()},
        contexts={"600000": _context()},
        today_orders=[],
        params={},
        now=datetime(2026, 5, 9, 10, 30, 0),
        used_order_count=0,
        max_orders=5,
        market_state="repair",
    )

    assert len(orders) == 1
    assert orders[0]["side"] == "buy"
    assert orders[0]["source"] == "auto_smart_t"
    assert orders[0]["signal_snapshot"]["smart_t_action"] == "positive_t_add"


def test_smart_t_add_order_skips_today_duplicate_buy() -> None:
    orders = build_smart_t_add_orders(
        account=_account(),
        positions=[_position()],
        prices={"600000": _quote()},
        contexts={"600000": _context()},
        today_orders=[{"symbol": "600000", "side": "buy", "status": "filled"}],
        params={},
        now=datetime(2026, 5, 9, 10, 30, 0),
        used_order_count=0,
        max_orders=5,
        market_state="repair",
    )

    assert orders == []


def test_smart_t_add_order_requires_strict_washout_volume_and_vwap() -> None:
    context = _context()
    context = PaperExitContext(**{**context.__dict__, "volume_release_ratio": 0.7})
    orders = build_smart_t_add_orders(
        account=_account(),
        positions=[_position()],
        prices={"600000": _quote(price=9.86)},
        contexts={"600000": context},
        today_orders=[],
        params={},
        now=datetime(2026, 5, 9, 10, 30, 0),
        used_order_count=0,
        max_orders=5,
        market_state="repair",
    )

    assert orders == []


def test_smart_t_add_order_skips_open_and_close_windows() -> None:
    for now in (datetime(2026, 5, 9, 9, 45, 0), datetime(2026, 5, 9, 14, 35, 0)):
        orders = build_smart_t_add_orders(
            account=_account(),
            positions=[_position()],
            prices={"600000": _quote()},
            contexts={"600000": _context()},
            today_orders=[],
            params={},
            now=now,
            used_order_count=0,
            max_orders=5,
            market_state="repair",
        )

        assert orders == []


def test_smart_t_add_order_skips_single_position_eval_error(monkeypatch) -> None:
    import app.services.paper.smart_t as smart_t_module

    def boom(*args, **kwargs):
        raise RuntimeError("bad context")

    monkeypatch.setattr(smart_t_module, "evaluate_paper_exit", boom)
    orders = build_smart_t_add_orders(
        account=_account(),
        positions=[_position()],
        prices={"600000": _quote()},
        contexts={"600000": _context()},
        today_orders=[],
        params={},
        now=datetime(2026, 5, 9, 10, 30, 0),
        used_order_count=0,
        max_orders=5,
        market_state="repair",
    )

    assert orders == []
