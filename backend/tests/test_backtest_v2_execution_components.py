from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.services.paper import matching as matching_module
from app.services.paper.fees import calculate_fee

broker_module = pytest.importorskip(
    "app.services.backtest.broker",
    reason="Backtest broker v2 is not implemented yet.",
)
portfolio_module = pytest.importorskip(
    "app.services.backtest.portfolio",
    reason="Backtest portfolio v2 is not implemented yet.",
)
data_provider_module = pytest.importorskip(
    "app.services.backtest.data_provider",
    reason="Backtest data provider v2 is not implemented yet.",
)


def test_data_provider_reports_missing_invalid_and_suspended_bars_without_blocking() -> None:
    provider_cls = getattr(data_provider_module, "DailyBarDataProvider")
    provider = provider_cls(db=object())
    histories = {
        "300001": [
            _bar("300001", "2025-01-02", open_price=0.0, close_price=10.0),
            _bar("300001", "2025-01-06", open_price=10.1, close_price=10.2, volume=0),
        ]
    }

    quality = provider.quality_report(
        symbols=["300001", "300002"],
        trade_dates=["2025-01-02", "2025-01-03", "2025-01-06"],
        histories=histories,
        start_date="2025-01-02",
        end_date="2025-01-06",
    )

    assert quality.symbol_count == 2
    assert quality.missing_symbol_count == 1
    assert quality.missing_bar_count == 4
    assert quality.invalid_bar_count == 1
    assert quality.suspended_bar_count == 2
    assert quality.warnings


def test_data_provider_manifest_records_hash_and_forward_adjustment_method() -> None:
    provider = getattr(data_provider_module, "DailyBarDataProvider")(db=object())

    manifest = provider.dataset_manifest(
        start_date="2025-01-02",
        end_date="2025-01-06",
        symbols=["300001"],
    )

    assert manifest["source_table"] == "daily_bar_snapshots"
    assert manifest["source_hash"]
    assert manifest["adjustment_method"] == "forward"


def test_data_provider_loads_or_derives_pre_close_from_daily_snapshot() -> None:
    row_with_pre_close = SimpleNamespace(
        symbol="300001",
        trade_date="2025-01-02",
        open_price=11.0,
        close_price=12.0,
        high_price=12.0,
        low_price=11.0,
        volume=1_000_000,
        amount=12_000_000,
        pct_chg=20.0,
        pre_close=10.0,
        instrument_type="stock",
        market="CN",
    )
    row_without_pre_close = SimpleNamespace(
        symbol="600001",
        trade_date="2025-01-02",
        open_price=10.8,
        close_price=11.0,
        high_price=11.0,
        low_price=10.8,
        volume=1_000_000,
        amount=11_000_000,
        pct_chg=10.0,
        instrument_type="stock",
        market="CN",
    )

    loaded = getattr(data_provider_module, "_bar_from_row")(row_with_pre_close)
    derived = getattr(data_provider_module, "_bar_from_row")(row_without_pre_close)

    assert loaded.pre_close == 10.0
    assert derived.pre_close == pytest.approx(10.0)


def test_daily_bar_vwap_fallback_does_not_use_same_day_high_low_close() -> None:
    bar = _bar(
        "300001",
        "2025-01-02",
        open_price=10.0,
        high_price=12.0,
        low_price=8.0,
        close_price=11.0,
        volume=1_000_000,
        amount=0.0,
    )

    assert bar.vwap == pytest.approx(10.0)


def test_broker_rejects_limit_up_limit_down_and_suspension_before_matching() -> None:
    broker = getattr(broker_module, "BacktestBroker")()
    request_cls = getattr(broker_module, "ExecutionRequest")

    limit_up = broker.execute(
        request_cls(
            trade_date="2025-01-02",
            symbol="600001",
            side="buy",
            quantity=1000,
            bar=_bar("600001", "2025-01-02", open_price=11.0, close_price=11.0, pct_chg=10.0),
            execution_model="open_price",
        )
    )
    suspended = broker.execute(
        request_cls(
            trade_date="2025-01-02",
            symbol="300002",
            side="buy",
            quantity=1000,
            bar=_bar("300002", "2025-01-02", open_price=10.0, close_price=10.0, volume=0),
            execution_model="open_price",
        )
    )
    limit_down = broker.execute(
        request_cls(
            trade_date="2025-01-02",
            symbol="600003",
            side="sell",
            quantity=1000,
            bar=_bar("600003", "2025-01-02", open_price=9.0, close_price=9.0, pct_chg=-10.0),
            execution_model="open_price",
        )
    )

    assert limit_up.status == "rejected"
    assert "涨停" in limit_up.reject_reason
    assert suspended.status == "rejected"
    assert "停牌" in suspended.reject_reason
    assert limit_down.status == "rejected"
    assert "跌停" in limit_down.reject_reason


def test_broker_uses_beijing_time_for_historical_matching(monkeypatch: pytest.MonkeyPatch) -> None:
    fixed_now = datetime(2030, 1, 2, 10, 0, 0)
    monkeypatch.setattr(broker_module, "beijing_now", lambda: fixed_now)
    monkeypatch.setattr(matching_module, "beijing_now", lambda: fixed_now)

    result = getattr(broker_module, "BacktestBroker")().execute(
        getattr(broker_module, "ExecutionRequest")(
            trade_date="2025-01-02",
            symbol="600001",
            side="buy",
            quantity=1000,
            bar=_bar("600001", "2025-01-02", open_price=10.0, close_price=10.1),
            execution_model="open_price",
        )
    )

    assert result.status == "filled"
    assert "行情时间过旧" not in result.reject_reason


def test_broker_applies_market_and_security_type_specific_limit_rules() -> None:
    broker = getattr(broker_module, "BacktestBroker")()
    request_cls = getattr(broker_module, "ExecutionRequest")

    etf_limit_move = broker.execute(
        request_cls(
            trade_date="2025-01-02",
            symbol="510300",
            side="buy",
            quantity=1000,
            bar=_bar(
                "510300",
                "2025-01-02",
                open_price=4.4,
                close_price=4.4,
                pct_chg=10.0,
                instrument_type="etf",
            ),
            execution_model="open_price",
        )
    )
    fund_limit_move = broker.execute(
        request_cls(
            trade_date="2025-01-02",
            symbol="160105",
            side="buy",
            quantity=1000,
            bar=_bar(
                "160105",
                "2025-01-02",
                open_price=1.1,
                close_price=1.1,
                pct_chg=10.0,
                instrument_type="fund",
            ),
            execution_model="open_price",
        )
    )
    gem_ten_pct_move = broker.execute(
        request_cls(
            trade_date="2025-01-02",
            symbol="300001",
            side="buy",
            quantity=1000,
            bar=_bar("300001", "2025-01-02", open_price=11.0, close_price=11.0, pct_chg=10.0),
            execution_model="open_price",
        )
    )
    gem_twenty_pct_move = broker.execute(
        request_cls(
            trade_date="2025-01-02",
            symbol="300001",
            side="buy",
            quantity=1000,
            bar=_bar("300001", "2025-01-02", open_price=12.0, close_price=12.0, pct_chg=20.0),
            execution_model="open_price",
        )
    )

    assert etf_limit_move.status == "filled"
    assert fund_limit_move.status == "filled"
    assert gem_ten_pct_move.status == "filled"
    assert gem_twenty_pct_move.status == "rejected"
    assert "涨停" in gem_twenty_pct_move.reject_reason


def test_broker_uses_real_limit_price_from_pre_close_not_selected_price() -> None:
    broker = getattr(broker_module, "BacktestBroker")()
    request_cls = getattr(broker_module, "ExecutionRequest")

    result = broker.execute(
        request_cls(
            trade_date="2025-01-02",
            symbol="300001",
            side="buy",
            quantity=1000,
            bar=_bar(
                "300001",
                "2025-01-02",
                open_price=11.0,
                close_price=12.0,
                high_price=12.0,
                low_price=11.0,
                pct_chg=20.0,
                pre_close=10.0,
            ),
            execution_model="open_price",
        )
    )

    assert result.status == "filled"
    assert result.requested_price == Decimal("11.0000")
    assert result.fill_price is not None
    assert result.fill_price > result.requested_price


def test_broker_market_impact_penalizes_large_daily_participation() -> None:
    broker = getattr(broker_module, "BacktestBroker")()
    request_cls = getattr(broker_module, "ExecutionRequest")

    result = broker.execute(
        request_cls(
            trade_date="2025-01-02",
            symbol="600001",
            side="buy",
            quantity=1000,
            bar=_bar(
                "600001",
                "2025-01-02",
                open_price=10.0,
                close_price=10.0,
                high_price=10.2,
                low_price=9.8,
                amount=100_000.0,
            ),
            execution_model="market_impact",
        )
    )

    assert result.status == "filled"
    assert result.execution_model == "market_impact"
    assert result.requested_price == Decimal("10.0800")
    assert result.fill_price is not None
    assert result.fill_price > result.requested_price


def test_portfolio_applies_stock_t1_unlock_and_etf_same_day_availability() -> None:
    config_cls = getattr(portfolio_module, "PortfolioConfig")
    portfolio_cls = getattr(portfolio_module, "BacktestPortfolio")
    portfolio = portfolio_cls(config_cls(initial_cash=Decimal("100000.00")))

    portfolio.buy(
        symbol="300001",
        name="Test Tech",
        quantity=1000,
        price=Decimal("10.00"),
        fee=calculate_fee(symbol="300001", side="buy", price=Decimal("10.00"), quantity=1000),
        trade_date="2025-01-02",
        next_trade_date="2025-01-03",
        strategy_key="first_board",
        stop_loss=9.5,
        take_profit=10.8,
        max_holding_days=2,
    )

    assert portfolio.positions["300001"].available_quantity("2025-01-02") == 0
    assert portfolio.positions["300001"].available_quantity("2025-01-03") == 1000

    portfolio.buy(
        symbol="510300",
        name="CSI300 ETF",
        quantity=1000,
        price=Decimal("4.00"),
        fee=calculate_fee(symbol="510300", side="buy", price=Decimal("4.00"), quantity=1000),
        trade_date="2025-01-03",
        next_trade_date="2025-01-06",
        strategy_key="etf_rotation",
        stop_loss=None,
        take_profit=None,
        max_holding_days=1,
    )

    assert portfolio.positions["510300"].available_quantity("2025-01-03") == 1000

    portfolio.buy(
        symbol="512999",
        name="Unknown Sector ETF",
        quantity=1000,
        price=Decimal("4.00"),
        fee=calculate_fee(symbol="512999", side="buy", price=Decimal("4.00"), quantity=1000),
        trade_date="2025-01-03",
        next_trade_date="2025-01-06",
        strategy_key="etf_rotation",
        stop_loss=None,
        take_profit=None,
        max_holding_days=1,
    )

    assert portfolio.positions["512999"].available_quantity("2025-01-03") == 0
    assert portfolio.positions["512999"].available_quantity("2025-01-06") == 1000


def _bar(
    symbol: str,
    trade_date: str,
    *,
    open_price: float = 10.0,
    close_price: float = 10.0,
    high_price: float | None = None,
    low_price: float | None = None,
    volume: int = 1_000_000,
    amount: float = 10_000_000.0,
    pct_chg: float = 0.0,
    pre_close: float | None = None,
    instrument_type: str = "stock",
    market: str = "CN",
):
    bar_cls = getattr(data_provider_module, "DailyBar")
    return bar_cls(
        symbol=symbol,
        trade_date=trade_date,
        open_price=open_price,
        close_price=close_price,
        high_price=high_price if high_price is not None else max(open_price, close_price),
        low_price=low_price if low_price is not None else min(open_price, close_price),
        volume=volume,
        amount=amount,
        pct_chg=pct_chg,
        pre_close=pre_close if pre_close is not None else (close_price / (1 + pct_chg / 100) if pct_chg != -100 else close_price),
        instrument_type=instrument_type,
        market=market,
    )
