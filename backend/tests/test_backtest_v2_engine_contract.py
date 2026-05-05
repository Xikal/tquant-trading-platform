from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import pytest

from app.services.paper.fees import calculate_fee

engine_module = pytest.importorskip(
    "app.services.backtest.engine",
    reason="BacktestEngine v2 is not implemented yet.",
)
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


class _ProviderStub:
    def fetch_trade_dates(self, start_date: str, end_date: str) -> list[str]:
        return [item for item in ["2025-01-02", "2025-01-03", "2025-01-06"] if start_date <= item <= end_date]

    def fetch_bars(self, symbols, *, start_date: str, end_date: str):  # noqa: ANN001
        return {
            symbol: [
                _bar(symbol, "2025-01-02", open_price=10.0, close_price=10.1, pct_chg=1.0),
                _bar(symbol, "2025-01-03", open_price=10.2, close_price=10.7, pct_chg=5.9),
                _bar(symbol, "2025-01-06", open_price=10.6, close_price=10.4, pct_chg=-2.8),
            ]
            for symbol in symbols
        }

    def load_low_buy_signals(
        self,
        *,
        strategies,
        start_date: str,
        end_date: str,
        max_signals_per_day: int = 20,  # noqa: ARG002
    ):
        signal_cls = getattr(data_provider_module, "BacktestSignal")
        if not strategies or not (start_date <= "2025-01-02" <= end_date):
            return []
        return [
            signal_cls(
                signal_date="2025-01-02",
                symbol="300001",
                strategy_key=strategies[0],
                score=88.0,
                name="Test Tech",
                signal_state="buy_now",
                entry_zone_high=10.2,
                stop_loss=9.7,
                take_profit=10.6,
                max_holding_days=1,
                position_pct=0.2,
            )
        ]

    def quality_report(
        self,
        *,
        symbols,
        trade_dates: list[str],
        histories,
        start_date: str,
        end_date: str,
    ):
        report_cls = getattr(data_provider_module, "DataQualityReport")
        return report_cls(
            version="daily_bar_snapshots:v1",
            start_date=start_date,
            end_date=end_date,
            symbol_count=len(list(symbols)),
            trade_date_count=len(trade_dates),
            missing_bar_count=0,
            invalid_bar_count=0,
            suspended_bar_count=0,
            warnings=[],
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


def test_broker_rejects_limit_up_limit_down_and_suspension_before_matching() -> None:
    broker = getattr(broker_module, "BacktestBroker")()
    request_cls = getattr(broker_module, "ExecutionRequest")

    limit_up = broker.execute(
        request_cls(
            trade_date="2025-01-02",
            symbol="300001",
            side="buy",
            quantity=1000,
            bar=_bar("300001", "2025-01-02", open_price=11.0, close_price=11.0, pct_chg=10.0),
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
            symbol="300003",
            side="sell",
            quantity=1000,
            bar=_bar("300003", "2025-01-02", open_price=9.0, close_price=9.0, pct_chg=-10.0),
            execution_model="open_price",
        )
    )

    assert limit_up.status == "rejected"
    assert "涨停" in limit_up.reject_reason
    assert suspended.status == "rejected"
    assert "停牌" in suspended.reject_reason
    assert limit_down.status == "rejected"
    assert "跌停" in limit_down.reject_reason


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


def test_engine_is_reproducible_and_outputs_trades_and_equity_curve() -> None:
    config = _config()
    first = getattr(engine_module, "BacktestEngine")(_ProviderStub()).run(config)
    second = getattr(engine_module, "BacktestEngine")(_ProviderStub()).run(config)

    assert _stable_result(first) == _stable_result(second)
    assert first.data_quality.version == "daily_bar_snapshots:v1"
    assert first.equity_curve
    assert first.orders
    assert any(order.status == "filled" for order in first.orders)
    assert first.trades
    assert first.metrics["trade_count"] >= 1
    assert {"trade_count", "total_return_pct", "max_drawdown_pct", "sharpe_ratio"} <= set(first.metrics)


def test_engine_cancel_preserves_partial_outputs_and_marks_cancelled() -> None:
    result = getattr(engine_module, "BacktestEngine")(_ProviderStub()).run(_config(), cancel_token=_CancelToken())

    assert result.status == "cancelled"
    assert result.equity_curve
    assert result.trades or result.partial is True


def test_engine_persists_manifest_quality_trades_and_equity_outputs() -> None:
    repository = _Repository()
    result = getattr(engine_module, "BacktestEngine")(
        _ProviderStub(),
        repository=repository,
    ).run(_config())

    assert result.version
    assert repository.manifests[0]["source_hash"]
    assert repository.quality_rows
    assert repository.trades
    assert repository.equity


def _config():
    config_cls = getattr(engine_module, "BacktestConfig")
    return config_cls(
        start_date="2025-01-02",
        end_date="2025-01-06",
        strategies=["first_board"],
        initial_cash=100000.0,
        execution_model="open_price",
        max_position_pct=0.2,
        max_positions=8,
        force_liquidate_at_end=True,
    )


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
    )


def _stable_result(value: Any) -> dict[str, Any]:
    payload = value.to_dict() if hasattr(value, "to_dict") else value
    ignored = {"started_at", "completed_at", "duration_seconds", "created_at"}
    return {key: item for key, item in payload.items() if key not in ignored}


@dataclass
class _CancelToken:
    cancelled: bool = True

    def is_cancelled(self) -> bool:
        return self.cancelled


@dataclass
class _Repository:
    manifests: list[dict[str, Any]]
    quality_rows: list[dict[str, Any]]
    trades: list[dict[str, Any]]
    equity: list[dict[str, Any]]

    def __init__(self) -> None:
        self.manifests = []
        self.quality_rows = []
        self.trades = []
        self.equity = []
