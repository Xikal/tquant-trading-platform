from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.entities import DailyBarSnapshot
from app.services.backtest.forward_path import enrich_trade_forward_path
from app.services.backtest.persistence import _build_execution_model_preview
from scripts.low_buy_market_backtest_reporting import portfolio_backtest_metrics


def test_execution_model_forward_path_uses_real_daily_bars_for_parity() -> None:
    db = _db()
    _seed_forward_bars(db, "600000")
    trade = _trade()

    path = enrich_trade_forward_path(db, trade)
    preview = _build_execution_model_preview(SimpleNamespace(trades=[trade]), db=db)
    canonical5 = portfolio_backtest_metrics([_outcome_from_preview_trade(trade, path.values)], max_positions=5)
    canonical10 = portfolio_backtest_metrics([_outcome_from_preview_trade(trade, path.values)], max_positions=10)

    assert path.status == "ok"
    assert path.values["return_1d"] == pytest.approx(1.0)
    assert path.values["return_5d"] == pytest.approx(5.0)
    assert path.values["max_gain_5d"] == pytest.approx(7.0)
    assert path.values["max_drawdown_5d"] == pytest.approx(-1.0)
    assert preview["replacement_enabled"] is False
    assert preview["final_fact_source"] == "portfolio_backtest_metrics"
    assert preview["max_5"]["portfolio_return_pct"] == canonical5["portfolio_return_pct"]
    assert preview["max_10"]["portfolio_return_pct"] == canonical10["portfolio_return_pct"]
    assert all(preview["parity"]["max_5"].values())
    assert all(preview["parity"]["max_10"].values())


def test_execution_model_forward_path_blocks_when_daily_bars_are_partial() -> None:
    db = _db()
    db.add(_bar("600000", "2026-01-02", close_price=101.0, high_price=102.0, low_price=99.0))
    db.commit()

    path = enrich_trade_forward_path(db, _trade())
    preview = _build_execution_model_preview(SimpleNamespace(trades=[_trade()]), db=db)

    assert path.status == "partial_path"
    assert preview["ok"] is False
    assert preview["blocked_reason"] == "partial_path"
    assert preview["replacement_enabled"] is False


def _db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return factory()


def _seed_forward_bars(db, symbol: str) -> None:  # noqa: ANN001
    for index, close_price in enumerate([101.0, 102.0, 103.0, 104.0, 105.0], start=2):
        db.add(
            _bar(
                symbol,
                f"2026-01-0{index}",
                close_price=close_price,
                high_price=100.0 + index + 1,
                low_price=99.0,
            )
        )
    db.commit()


def _bar(symbol: str, trade_date: str, *, close_price: float, high_price: float, low_price: float) -> DailyBarSnapshot:
    return DailyBarSnapshot(
        symbol=symbol,
        trade_date=trade_date,
        instrument_type="stock",
        open_price=100.0,
        close_price=close_price,
        high_price=high_price,
        low_price=low_price,
        volume=1000,
        amount=100000,
        pct_chg=0.0,
        is_suspended=False,
        is_delisted=False,
    )


def _trade():
    return SimpleNamespace(
        symbol="600000",
        name="浦发银行",
        strategy_key="first_board",
        entry_date="2026-01-01",
        exit_date="2026-01-06",
        entry_price=100.0,
        exit_price=105.0,
        return_pct=5.0,
        exit_reason="max_holding_days",
    )


def _outcome_from_preview_trade(trade, path: dict[str, float]):  # noqa: ANN001
    from scripts.low_buy_market_backtest_reporting import TradeOutcome

    return TradeOutcome(
        symbol=trade.symbol,
        name=trade.name,
        signal_date=trade.entry_date,
        strategy_key=trade.strategy_key,
        buy_signal_state="buy_now",
        entry_price=trade.entry_price,
        execution_status="filled",
        net_return_pct=trade.return_pct,
        execution_exit_reason=trade.exit_reason,
        return_1d=path["return_1d"],
        return_2d=path["return_2d"],
        return_3d=path["return_3d"],
        return_4d=path["return_4d"],
        return_5d=path["return_5d"],
        max_gain_5d=path["max_gain_5d"],
        max_drawdown_5d=path["max_drawdown_5d"],
        entry_trade_date=trade.entry_date,
        exit_trade_date=trade.exit_date,
    )
