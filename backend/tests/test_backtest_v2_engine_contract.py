from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import pytest

from app.services.backtest.analyzer import BacktestAnalyzer

engine_module = pytest.importorskip(
    "app.services.backtest.engine",
    reason="BacktestEngine v2 is not implemented yet.",
)
data_provider_module = pytest.importorskip(
    "app.services.backtest.data_provider",
    reason="Backtest data provider v2 is not implemented yet.",
)
persistence_module = pytest.importorskip(
    "app.services.backtest.persistence",
    reason="Backtest persistence v2 is not implemented yet.",
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


class _BenchmarkProvider(_ProviderStub):
    def fetch_bars(self, symbols, *, start_date: str, end_date: str):  # noqa: ANN001
        histories = super().fetch_bars(symbols, start_date=start_date, end_date=end_date)
        if "000905" in {str(symbol) for symbol in symbols}:
            histories["000905"] = [
                _bar("000905", "2025-01-02", open_price=100.0, close_price=100.0, pct_chg=0.0),
                _bar("000905", "2025-01-03", open_price=101.0, close_price=102.0, pct_chg=2.0),
                _bar("000905", "2025-01-06", open_price=102.0, close_price=101.0, pct_chg=-0.9804),
            ]
        return histories


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
    assert all(trade.holding_days >= 1 for trade in first.trades)
    assert all(trade.fee_amount > 0 for trade in first.trades)
    assert all(order.requested_price is not None for order in first.orders if order.status == "filled")
    assert first.metrics["trade_count"] >= 1
    assert {"trade_count", "total_return_pct", "max_drawdown_pct", "sharpe_ratio"} <= set(first.metrics)
    assumptions = first.to_dict()["execution_assumptions"]
    assert assumptions["fee_model"]["version"] == "paper_fee_v2"
    assert "0.0085%" in assumptions["fee_model"]["commission"]
    assert "0.005%" in assumptions["fee_model"]["commission"]
    assert assumptions["price_limit_handling"]
    assert assumptions["same_bar_path"]
    assert first.metrics["execution_assumptions"]["execution_model"] == config.execution_model


def test_engine_loads_real_benchmark_curve_and_uses_it_for_alpha_ir() -> None:
    config_cls = getattr(engine_module, "BacktestConfig")
    config = config_cls(
        start_date="2025-01-02",
        end_date="2025-01-06",
        benchmark_symbol="000905",
        strategies=["first_board"],
        initial_cash=100000.0,
        execution_model="open_price",
        max_position_pct=0.2,
        max_positions=8,
        force_liquidate_at_end=True,
    )

    result = getattr(engine_module, "BacktestEngine")(_BenchmarkProvider()).run(config)

    assert [item.benchmark_symbol for item in result.equity_curve] == ["000905", "000905", "000905"]
    assert [item.benchmark_close for item in result.equity_curve] == [100.0, 102.0, 101.0]
    assert result.equity_curve[1].benchmark_return_pct == pytest.approx(2.0)
    assert result.equity_curve[-1].benchmark_nav == pytest.approx(101000.0)
    assert result.metrics["benchmark_return_pct"] == pytest.approx(1.0)
    assert result.metrics["benchmark_alpha_pct"] == pytest.approx(
        result.metrics["total_return_pct"] - result.metrics["benchmark_return_pct"],
        abs=0.0001,
    )
    assert result.metrics["benchmark_alpha_pct"] != pytest.approx(result.metrics["total_return_pct"])
    assert result.metrics["information_ratio"] != 0.0


def test_analyzer_outputs_extended_performance_metrics_against_benchmark() -> None:
    snapshots = [
        SimpleNamespace(total_equity=100000.0, benchmark_return_pct=0.0),
        SimpleNamespace(total_equity=102000.0, benchmark_return_pct=1.0),
        SimpleNamespace(total_equity=101000.0, benchmark_return_pct=-0.2),
        SimpleNamespace(total_equity=104000.0, benchmark_return_pct=0.5),
        SimpleNamespace(total_equity=103000.0, benchmark_return_pct=-0.1),
    ]

    metrics = BacktestAnalyzer().analyze(
        initial_cash=100000.0,
        equity_curve=snapshots,
        trades=[],
        orders=[],
    )

    assert {
        "sortino_ratio",
        "calmar_ratio",
        "benchmark_return_pct",
        "benchmark_alpha_pct",
        "information_ratio",
    } <= set(metrics)
    assert metrics["benchmark_return_pct"] == pytest.approx(1.2008, abs=0.0001)
    assert metrics["benchmark_alpha_pct"] == pytest.approx(1.7992, abs=0.0001)
    assert metrics["sortino_ratio"] > metrics["sharpe_ratio"]
    assert metrics["calmar_ratio"] > 0
    assert metrics["information_ratio"] > 0


def test_persistence_writes_benchmark_fields_to_daily_snapshots() -> None:
    db = _FakePersistenceDb()
    result = SimpleNamespace(
        equity_curve=[
            SimpleNamespace(
                trade_date="2025-01-02",
                cash=90000.0,
                market_value=10000.0,
                total_equity=100000.0,
                position_count=1,
                benchmark_symbol="000905",
                benchmark_close=100.0,
                benchmark_return_pct=0.0,
                benchmark_nav=100000.0,
            ),
            SimpleNamespace(
                trade_date="2025-01-03",
                cash=90000.0,
                market_value=10500.0,
                total_equity=100500.0,
                position_count=1,
                benchmark_symbol="000905",
                benchmark_close=102.0,
                benchmark_return_pct=2.0,
                benchmark_nav=102000.0,
            ),
        ]
    )

    getattr(persistence_module, "BacktestResultPersistence")(db)._create_equity_snapshots(7, result)

    assert len(db.rows) == 2
    assert db.rows[1].benchmark_symbol == "000905"
    assert db.rows[1].benchmark_close == pytest.approx(102.0)
    assert db.rows[1].benchmark_return_pct == pytest.approx(2.0)


def test_engine_records_trading_day_holding_days_across_weekend() -> None:
    signal_cls = getattr(data_provider_module, "BacktestSignal")
    config_cls = getattr(engine_module, "BacktestConfig")
    config = config_cls(
        start_date="2025-01-02",
        end_date="2025-01-06",
        signals=[
            signal_cls(
                signal_date="2025-01-02",
                symbol="300001",
                strategy_key="first_board",
                score=88.0,
                name="Test Tech",
                signal_state="buy_now",
                max_holding_days=10,
                position_pct=0.2,
            )
        ],
        initial_cash=100000.0,
        execution_model="open_price",
        force_liquidate_at_end=True,
    )

    result = getattr(engine_module, "BacktestEngine")(_ProviderStub()).run(config)

    assert result.trades
    assert result.trades[0].entry_date == "2025-01-03"
    assert result.trades[0].exit_date == "2025-01-06"
    assert result.trades[0].holding_days == 1


def test_engine_enters_signals_on_next_trade_date_and_skips_final_day_signal() -> None:
    signal_cls = getattr(data_provider_module, "BacktestSignal")
    config_cls = getattr(engine_module, "BacktestConfig")
    result = getattr(engine_module, "BacktestEngine")(_ProviderStub()).run(
        config_cls(
            start_date="2025-01-02",
            end_date="2025-01-06",
            signals=[
                signal_cls(
                    signal_date="2025-01-02",
                    symbol="300001",
                    strategy_key="first_board",
                    score=88.0,
                    signal_state="buy_now",
                    position_pct=0.2,
                ),
                signal_cls(
                    signal_date="2025-01-06",
                    symbol="300001",
                    strategy_key="first_board",
                    score=99.0,
                    signal_state="buy_now",
                    position_pct=0.2,
                ),
            ],
            initial_cash=100000.0,
            execution_model="open_price",
            force_liquidate_at_end=True,
        )
    )

    filled_buys = [order for order in result.orders if order.side == "buy" and order.status == "filled"]
    assert [order.trade_date for order in filled_buys] == ["2025-01-03"]


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
    assert repository.trades[0]["holding_days"] >= 1
    assert repository.trades[0]["fee_amount"] > 0
    assert repository.equity


def test_engine_outputs_industry_market_state_and_data_quality_attribution() -> None:
    result = getattr(engine_module, "BacktestEngine")(_AttributionProvider()).run(_attribution_config())
    payload = result.to_dict()

    attribution = payload["attribution"]
    assert payload["metrics"]["attribution"] == attribution
    assert attribution["version"] == "backtest-attribution-v1"
    assert attribution["data_quality_summary"]["quality_tag"] == "warning"

    industry = {bucket["bucket"]: bucket for bucket in attribution["industry"]}
    market_state = {bucket["bucket"]: bucket for bucket in attribution["market_state"]}
    data_quality = {bucket["bucket"]: bucket for bucket in attribution["data_quality"]}
    failure_reasons = {bucket["bucket"]: bucket for bucket in attribution["failure_reasons"]}

    assert industry["软件"]["signal_count"] == 1
    assert industry["软件"]["trade_count"] == 1
    assert industry["软件"]["win_rate_pct"] == 100.0
    assert market_state["repair"]["trade_count"] == 1
    assert data_quality["ok"]["trade_count"] == 1
    assert data_quality["missing_bar"]["rejected_order_count"] == 1
    assert failure_reasons


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


def _attribution_config():
    config_cls = getattr(engine_module, "BacktestConfig")
    signal_cls = getattr(data_provider_module, "BacktestSignal")
    return config_cls(
        start_date="2025-01-02",
        end_date="2025-01-06",
        signals=[
            signal_cls(
                signal_date="2025-01-02",
                symbol="300001",
                strategy_key="first_board",
                score=90.0,
                name="软件龙头",
                entry_zone_high=10.2,
                stop_loss=9.5,
                take_profit=10.5,
                max_holding_days=1,
                position_pct=0.2,
                metadata={
                    "sector_name": "软件",
                    "market_state": "repair",
                },
            ),
            signal_cls(
                signal_date="2025-01-02",
                symbol="300002",
                strategy_key="first_board",
                score=80.0,
                name="硬件跟随",
                entry_zone_high=20.2,
                stop_loss=19.0,
                take_profit=21.0,
                max_holding_days=1,
                position_pct=0.2,
                metadata={
                    "industry": "硬件",
                    "market_state": "risk_release",
                },
            ),
        ],
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


class _FakePersistenceDb:
    def __init__(self) -> None:
        self.rows = []

    def add(self, row) -> None:  # noqa: ANN001
        self.rows.append(row)


class _AttributionProvider:
    def fetch_trade_dates(self, start_date: str, end_date: str) -> list[str]:
        return [item for item in ["2025-01-02", "2025-01-03", "2025-01-06"] if start_date <= item <= end_date]

    def fetch_bars(self, symbols, *, start_date: str, end_date: str):  # noqa: ANN001
        output = {
            "300001": [
                _bar("300001", "2025-01-02", open_price=10.0, close_price=10.1, pct_chg=1.0),
                _bar("300001", "2025-01-03", open_price=10.6, close_price=10.7, pct_chg=5.9),
                _bar("300001", "2025-01-06", open_price=10.9, close_price=10.8, pct_chg=0.9),
            ],
            "300002": [
                _bar("300002", "2025-01-06", open_price=20.2, close_price=20.3, pct_chg=1.0),
            ],
        }
        return {symbol: output[symbol] for symbol in symbols if symbol in output}

    def load_low_buy_signals(self, **kwargs):  # noqa: ANN003
        return []

    def quality_report(
        self,
        *,
        symbols,
        trade_dates: list[str],
        histories,
        start_date: str,
        end_date: str,
    ):
        provider = getattr(data_provider_module, "DailyBarDataProvider")(db=object())
        return provider.quality_report(
            symbols=symbols,
            trade_dates=trade_dates,
            histories=histories,
            start_date=start_date,
            end_date=end_date,
        )
