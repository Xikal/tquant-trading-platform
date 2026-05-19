from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from typing import Any

from app.services.backtest.analyzer import BacktestAnalyzer
from app.services.backtest.attribution import build_backtest_attribution
from app.services.backtest.broker import BacktestBroker, ExecutionModel, ExecutionRequest, ExecutionResult
from app.services.backtest.data_provider import BacktestSignal, DailyBar, DailyBarDataProvider, DataQualityReport
from app.services.backtest.engine_helpers import (
    bars_by_date as _bars_by_date,
    benchmark_curve as _benchmark_curve,
    cancel_requested as _cancel_requested,
    close_prices as _close_prices,
    config_dict as _config_dict,
    dataset_manifest as _dataset_manifest,
    dedupe_signals as _dedupe_signals,
    entry_estimated_price as _entry_estimated_price,
    execution_assumptions as _execution_assumptions,
    exit_plan as _exit_plan,
    next_trade_dates as _next_trade_dates,
    normalize_benchmark_symbol as _normalize_benchmark_symbol,
    signals_by_entry_date as _signals_by_entry_date,
    timeout_requested as _timeout_requested,
)
from app.services.backtest.portfolio import BacktestPortfolio, PortfolioConfig, PortfolioSnapshot, RealizedTrade
from app.services.paper.money import to_decimal


BACKTEST_ENGINE_VERSION = "backtest-core-v2.0"


@dataclass(frozen=True)
class BacktestConfig:
    start_date: str
    end_date: str
    benchmark_symbol: str = "000300"
    strategies: list[str] = field(default_factory=list)
    signals: list[BacktestSignal] = field(default_factory=list)
    initial_cash: float = 100000.0
    execution_model: str = ExecutionModel.CONSERVATIVE_SLIPPAGE.value
    max_position_pct: float = 0.2
    max_positions: int = 8
    max_signals_per_day: int = 20
    entry_delay_days: int = 1
    lot_size: int = 100
    force_liquidate_at_end: bool = True
    max_duration_seconds: int = 1800


@dataclass(frozen=True)
class BacktestOrder:
    trade_date: str
    symbol: str
    side: str
    quantity: int
    status: str
    strategy_key: str = ""
    execution_model: str = ""
    requested_price: float | None = None
    fill_price: float | None = None
    reject_reason: str = ""
    reason: str = ""


@dataclass(frozen=True)
class BacktestResult:
    version: str
    config: dict[str, Any]
    data_quality: DataQualityReport
    metrics: dict[str, Any]
    equity_curve: list[PortfolioSnapshot]
    orders: list[BacktestOrder]
    trades: list[RealizedTrade]
    attribution: dict[str, Any] = field(default_factory=dict)
    status: str = "succeeded"
    partial: bool = False
    dataset_manifest: dict[str, Any] = field(default_factory=dict)
    execution_assumptions: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "status": self.status,
            "partial": self.partial,
            "config": self.config,
            "dataset_manifest": self.dataset_manifest,
            "execution_assumptions": self.execution_assumptions,
            "data_quality": asdict(self.data_quality),
            "metrics": self.metrics,
            "attribution": self.attribution,
            "equity_curve": [asdict(item) for item in self.equity_curve],
            "orders": [asdict(item) for item in self.orders],
            "trades": [asdict(item) for item in self.trades],
        }


class BacktestEngine:
    def __init__(
        self,
        data_provider: DailyBarDataProvider,
        *,
        broker: BacktestBroker | None = None,
        analyzer: BacktestAnalyzer | None = None,
        repository: Any | None = None,
    ) -> None:
        self.data_provider = data_provider
        self.broker = broker or BacktestBroker()
        self.analyzer = analyzer or BacktestAnalyzer()
        self.repository = repository

    def run(
        self,
        config: BacktestConfig,
        *,
        cancel_token: Any | None = None,
        histories_override: dict[str, list[DailyBar]] | None = None,
        trade_dates_override: list[str] | None = None,
    ) -> BacktestResult:
        signals = list(config.signals) or self.data_provider.load_low_buy_signals(
            strategies=config.strategies,
            start_date=config.start_date,
            end_date=config.end_date,
            max_signals_per_day=config.max_signals_per_day,
        )
        symbols = sorted({signal.symbol for signal in signals})
        benchmark_symbol = _normalize_benchmark_symbol(config.benchmark_symbol)
        data_symbols = sorted({*symbols, *([benchmark_symbol] if benchmark_symbol else [])})
        trade_dates = (
            list(trade_dates_override)
            if trade_dates_override is not None
            else self.data_provider.fetch_trade_dates(config.start_date, config.end_date)
        )
        histories = (
            histories_override
            if histories_override is not None
            else self.data_provider.fetch_bars(data_symbols, start_date=config.start_date, end_date=config.end_date)
        )
        manifest = _dataset_manifest(self.data_provider, config, data_symbols)
        quality = self.data_provider.quality_report(
            symbols=data_symbols,
            trade_dates=trade_dates,
            histories=histories,
            start_date=config.start_date,
            end_date=config.end_date,
        )
        bars_by_date = _bars_by_date(histories)
        benchmark_by_date = _benchmark_curve(
            trade_dates=trade_dates,
            histories=histories,
            benchmark_symbol=benchmark_symbol,
            initial_cash=config.initial_cash,
        )
        signals_by_date = _signals_by_entry_date(signals, trade_dates, config.entry_delay_days)
        portfolio = BacktestPortfolio(
            PortfolioConfig(
                initial_cash=Decimal(str(config.initial_cash)),
                max_position_pct=config.max_position_pct,
                max_positions=config.max_positions,
                lot_size=config.lot_size,
            )
        )
        orders: list[BacktestOrder] = []
        equity_curve: list[PortfolioSnapshot] = []
        next_trade_dates = _next_trade_dates(trade_dates)
        cancelled = False
        timed_out = False
        started_monotonic = time.monotonic()
        for trade_date in trade_dates:
            bars_for_day = bars_by_date.get(trade_date, {})
            benchmark = benchmark_by_date.get(trade_date, {})
            if _timeout_requested(started_monotonic, config.max_duration_seconds) or _cancel_requested(cancel_token):
                timed_out = _timeout_requested(started_monotonic, config.max_duration_seconds) or bool(
                    getattr(cancel_token, "timed_out", False)
                )
                cancelled = not timed_out
                if not equity_curve:
                    equity_curve.append(
                        portfolio.snapshot(
                            trade_date,
                            _close_prices(bars_for_day),
                            benchmark_symbol=str(benchmark.get("benchmark_symbol") or ""),
                            benchmark_close=float(benchmark.get("benchmark_close") or 0.0),
                            benchmark_return_pct=float(benchmark.get("benchmark_return_pct") or 0.0),
                            benchmark_nav=float(benchmark.get("benchmark_nav") or 0.0),
                        )
                    )
                break
            self._run_exits(
                portfolio=portfolio,
                bars_for_day=bars_for_day,
                trade_date=trade_date,
                trade_dates=trade_dates,
                orders=orders,
                execution_model=config.execution_model,
                force_liquidate=config.force_liquidate_at_end and trade_date == trade_dates[-1],
            )
            self._run_entries(
                portfolio=portfolio,
                signals=signals_by_date.get(trade_date, []),
                bars_for_day=bars_for_day,
                trade_date=trade_date,
                next_trade_date=next_trade_dates.get(trade_date),
                config=config,
                orders=orders,
            )
            prices = _close_prices(bars_for_day)
            equity_curve.append(
                portfolio.snapshot(
                    trade_date,
                    prices,
                    benchmark_symbol=str(benchmark.get("benchmark_symbol") or ""),
                    benchmark_close=float(benchmark.get("benchmark_close") or 0.0),
                    benchmark_return_pct=float(benchmark.get("benchmark_return_pct") or 0.0),
                    benchmark_nav=float(benchmark.get("benchmark_nav") or 0.0),
                )
            )
            if _cancel_requested(cancel_token):
                timed_out = bool(getattr(cancel_token, "timed_out", False))
                cancelled = not timed_out
                break
        metrics = self.analyzer.analyze(
            initial_cash=config.initial_cash,
            equity_curve=equity_curve,
            trades=portfolio.realized_trades,
            orders=orders,
        )
        attribution = build_backtest_attribution(
            signals=signals,
            histories=histories,
            trade_dates=trade_dates,
            data_quality=quality,
            orders=orders,
            trades=portfolio.realized_trades,
        )
        metrics = dict(metrics)
        execution_assumptions = _execution_assumptions(config)
        metrics["attribution"] = attribution
        metrics["execution_assumptions"] = execution_assumptions
        result = BacktestResult(
            version=BACKTEST_ENGINE_VERSION,
            config=_config_dict(config),
            dataset_manifest=manifest,
            execution_assumptions=execution_assumptions,
            data_quality=quality,
            metrics=metrics,
            equity_curve=equity_curve,
            orders=orders,
            trades=portfolio.realized_trades,
            attribution=attribution,
            status="timeout" if timed_out else "cancelled" if cancelled else "succeeded",
            partial=cancelled or timed_out,
        )
        _persist_repository(self.repository, result)
        return result

    def _run_exits(
        self,
        *,
        portfolio: BacktestPortfolio,
        bars_for_day: dict[str, DailyBar],
        trade_date: str,
        trade_dates: list[str],
        orders: list[BacktestOrder],
        execution_model: str,
        force_liquidate: bool,
    ) -> None:
        for symbol, position in list(portfolio.positions.items()):
            bar = bars_for_day.get(symbol)
            if bar is None:
                orders.append(_order_reject(trade_date, symbol, "sell", 0, "缺少退出日线数据。"))
                continue
            exit_plan = _exit_plan(position, bar, trade_date, trade_dates, force_liquidate=force_liquidate)
            if exit_plan is None:
                continue
            quantity = position.available_quantity(trade_date)
            if quantity <= 0:
                orders.append(_order_reject(trade_date, symbol, "sell", position.quantity, "T+1 可卖数量不足。"))
                continue
            result = self.broker.execute(
                ExecutionRequest(
                    trade_date=trade_date,
                    symbol=symbol,
                    side="sell",
                    quantity=quantity,
                    bar=bar,
                    execution_model=execution_model,
                    requested_price=exit_plan["price"],
                    reason=exit_plan["reason"],
                )
            )
            orders.append(_order_from_execution(result, strategy_key=position.strategy_key))
            if result.status == "filled" and result.fill_price is not None and result.fee_detail is not None:
                portfolio.sell(
                    symbol=symbol,
                    quantity=result.quantity,
                    price=result.fill_price,
                    fee=result.fee_detail,
                    trade_date=trade_date,
                    exit_reason=exit_plan["reason"],
                    holding_days=exit_plan["holding_days"],
                )

    def _run_entries(
        self,
        *,
        portfolio: BacktestPortfolio,
        signals: list[BacktestSignal],
        bars_for_day: dict[str, DailyBar],
        trade_date: str,
        next_trade_date: str | None,
        config: BacktestConfig,
        orders: list[BacktestOrder],
    ) -> None:
        prices = {symbol: bar.close_price for symbol, bar in bars_for_day.items()}
        equity = portfolio.total_equity(prices)
        for signal in _dedupe_signals(signals):
            bar = bars_for_day.get(signal.symbol)
            if bar is None:
                orders.append(_order_reject(trade_date, signal.symbol, "buy", 0, "缺少入场日线数据。", signal))
                continue
            if not portfolio.can_open(signal.symbol):
                orders.append(_order_reject(trade_date, signal.symbol, "buy", 0, "超过最大持仓数或同标的已持仓。", signal))
                continue
            estimated_price = _entry_estimated_price(bar, signal, config.execution_model)
            quantity = portfolio.target_quantity(
                price=to_decimal(estimated_price),
                equity=equity,
                position_pct=signal.position_pct,
            )
            quantity = self._cash_safe_quantity(
                symbol=signal.symbol,
                quantity=quantity,
                price=to_decimal(estimated_price),
                cash=portfolio.cash,
                lot_size=config.lot_size,
            )
            if quantity <= 0:
                orders.append(_order_reject(trade_date, signal.symbol, "buy", 0, "现金不足或目标仓位过小。", signal))
                continue
            result = self.broker.execute(
                ExecutionRequest(
                    trade_date=trade_date,
                    symbol=signal.symbol,
                    side="buy",
                    quantity=quantity,
                    bar=bar,
                    execution_model=config.execution_model,
                    signal=signal,
                    reason="entry",
                )
            )
            orders.append(_order_from_execution(result))
            if result.status != "filled" or result.fill_price is None or result.fee_detail is None:
                continue
            if result.fee_detail.net_amount > portfolio.cash:
                orders.append(_order_reject(trade_date, signal.symbol, "buy", quantity, "成交含费金额超过可用现金。", signal))
                continue
            portfolio.buy(
                symbol=signal.symbol,
                name=signal.name,
                quantity=result.quantity,
                price=result.fill_price,
                fee=result.fee_detail,
                trade_date=trade_date,
                next_trade_date=next_trade_date,
                strategy_key=signal.strategy_key,
                stop_loss=signal.stop_loss,
                take_profit=signal.take_profit,
                max_holding_days=signal.max_holding_days,
            )

    @staticmethod
    def _cash_safe_quantity(
        *,
        symbol: str,
        quantity: int,
        price: Decimal,
        cash: Decimal,
        lot_size: int,
    ) -> int:
        from app.services.paper.fees import calculate_fee

        safe_quantity = quantity
        while safe_quantity > 0:
            fee = calculate_fee(symbol=symbol, side="buy", price=price, quantity=safe_quantity)
            if fee.net_amount <= cash:
                return safe_quantity
            safe_quantity -= max(lot_size, 1)
        return 0


def _persist_repository(repository: Any | None, result: BacktestResult) -> None:
    if repository is None:
        return
    _append_repository(repository, "manifests", result.dataset_manifest)
    _append_repository(repository, "quality_rows", asdict(result.data_quality))
    for item in result.trades:
        _append_repository(repository, "trades", asdict(item))
    for item in result.equity_curve:
        _append_repository(repository, "equity", asdict(item))


def _append_repository(repository: Any, attr_name: str, payload: dict[str, Any]) -> None:
    target = getattr(repository, attr_name, None)
    if isinstance(target, list):
        target.append(payload)
        return
    method = getattr(repository, f"append_{attr_name}", None)
    if callable(method):
        method(payload)


def _order_from_execution(result: ExecutionResult, *, strategy_key: str | None = None) -> BacktestOrder:
    return BacktestOrder(
        trade_date=result.trade_date,
        symbol=result.symbol,
        side=result.side,
        quantity=result.quantity,
        status=result.status,
        strategy_key=strategy_key if strategy_key is not None else result.strategy_key,
        execution_model=result.execution_model,
        requested_price=float(result.requested_price) if result.requested_price is not None else None,
        fill_price=float(result.fill_price) if result.fill_price is not None else None,
        reject_reason=result.reject_reason,
        reason=result.reason,
    )


def _order_reject(
    trade_date: str,
    symbol: str,
    side: str,
    quantity: int,
    reason: str,
    signal: BacktestSignal | None = None,
) -> BacktestOrder:
    return BacktestOrder(
        trade_date=trade_date,
        symbol=symbol,
        side=side,
        quantity=quantity,
        status="rejected",
        strategy_key=signal.strategy_key if signal else "",
        reject_reason=reason,
    )
