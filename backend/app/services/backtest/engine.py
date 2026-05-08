from __future__ import annotations

import hashlib
import time
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from typing import Any

from app.services.backtest.analyzer import BacktestAnalyzer
from app.services.backtest.attribution import build_backtest_attribution
from app.services.backtest.broker import BacktestBroker, ExecutionModel, ExecutionRequest, ExecutionResult
from app.services.backtest.data_provider import BacktestSignal, DailyBar, DailyBarDataProvider, DataQualityReport
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
    entry_delay_days: int = 0
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
                    execution_model=ExecutionModel.CLOSE_PRICE.value,
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


def _bars_by_date(histories: dict[str, list[DailyBar]]) -> dict[str, dict[str, DailyBar]]:
    output: dict[str, dict[str, DailyBar]] = {}
    for symbol, bars in histories.items():
        for bar in bars:
            output.setdefault(bar.trade_date, {})[symbol] = bar
    return output


def _signals_by_entry_date(
    signals: list[BacktestSignal],
    trade_dates: list[str],
    entry_delay_days: int,
) -> dict[str, list[BacktestSignal]]:
    index_by_date = {trade_date: index for index, trade_date in enumerate(trade_dates)}
    output: dict[str, list[BacktestSignal]] = {}
    for signal in signals:
        index = index_by_date.get(signal.signal_date)
        if index is None:
            continue
        entry_index = min(index + max(entry_delay_days, 0), len(trade_dates) - 1)
        output.setdefault(trade_dates[entry_index], []).append(signal)
    return output


def _dedupe_signals(signals: list[BacktestSignal]) -> list[BacktestSignal]:
    best_by_symbol: dict[str, BacktestSignal] = {}
    for signal in signals:
        current = best_by_symbol.get(signal.symbol)
        if current is None or (signal.score, signal.strategy_key) > (current.score, current.strategy_key):
            best_by_symbol[signal.symbol] = signal
    return sorted(best_by_symbol.values(), key=lambda item: (item.score, item.strategy_key, item.symbol), reverse=True)


def _next_trade_dates(trade_dates: list[str]) -> dict[str, str | None]:
    return {
        trade_date: trade_dates[index + 1] if index + 1 < len(trade_dates) else None
        for index, trade_date in enumerate(trade_dates)
    }


def _close_prices(bars_for_day: dict[str, DailyBar]) -> dict[str, float]:
    return {symbol: bar.close_price for symbol, bar in bars_for_day.items()}


def _normalize_benchmark_symbol(value: str | None) -> str:
    return str(value or "").strip()


def _benchmark_curve(
    *,
    trade_dates: list[str],
    histories: dict[str, list[DailyBar]],
    benchmark_symbol: str,
    initial_cash: float,
) -> dict[str, dict[str, float | str]]:
    if not benchmark_symbol:
        return {}
    bars_by_trade_date = {bar.trade_date: bar for bar in histories.get(benchmark_symbol, []) if bar.close_price > 0}
    first_close = 0.0
    previous_close = 0.0
    output: dict[str, dict[str, float | str]] = {}
    for trade_date in trade_dates:
        bar = bars_by_trade_date.get(trade_date)
        close = float(bar.close_price) if bar is not None else previous_close
        if close > 0 and first_close <= 0:
            first_close = close
        return_pct = 0.0 if previous_close <= 0 or close <= 0 else (close / previous_close - 1) * 100
        nav = 0.0 if first_close <= 0 or close <= 0 else float(initial_cash) * close / first_close
        output[trade_date] = {
            "benchmark_symbol": benchmark_symbol,
            "benchmark_close": close,
            "benchmark_return_pct": return_pct,
            "benchmark_nav": nav,
        }
        if close > 0:
            previous_close = close
    return output


def _cancel_requested(cancel_token: Any | None) -> bool:
    if cancel_token is None:
        return False
    checker = getattr(cancel_token, "is_cancelled", None)
    if callable(checker):
        return bool(checker())
    return bool(getattr(cancel_token, "cancelled", False))


def _timeout_requested(started_monotonic: float, max_duration_seconds: int | float | None) -> bool:
    if max_duration_seconds is None or max_duration_seconds <= 0:
        return False
    return time.monotonic() - started_monotonic >= float(max_duration_seconds)


def _dataset_manifest(
    data_provider: DailyBarDataProvider,
    config: BacktestConfig,
    symbols: list[str],
) -> dict[str, Any]:
    resolver = getattr(data_provider, "dataset_manifest", None)
    if callable(resolver):
        return dict(
            resolver(
                start_date=config.start_date,
                end_date=config.end_date,
                symbols=symbols,
            )
            or {}
        )
    source_hash = hashlib.sha256(
        "|".join(
            [
                "daily_bar_snapshots",
                "forward",
                config.start_date,
                config.end_date,
                *sorted(symbols),
            ]
        ).encode("utf-8")
    ).hexdigest()
    return {
        "dataset_key": f"daily_bar_snapshots:{config.start_date}:{config.end_date}:{len(symbols)}",
        "source_table": "daily_bar_snapshots",
        "source_hash": source_hash,
        "manifest_hash": source_hash,
        "adjustment_method": "forward",
        "start_date": config.start_date,
        "end_date": config.end_date,
        "instrument_count": len(symbols),
        "bar_count": 0,
    }


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


def _entry_estimated_price(bar: DailyBar, signal: BacktestSignal, execution_model: str) -> float:
    if execution_model == ExecutionModel.OPEN_PRICE.value:
        return bar.open_price
    if execution_model == ExecutionModel.VWAP.value:
        return bar.vwap
    if execution_model == ExecutionModel.CLOSE_PRICE.value:
        return bar.close_price
    if execution_model == ExecutionModel.ENTRY_ZONE_TOUCH.value and signal.entry_zone_high:
        return signal.entry_zone_high
    return max(bar.open_price, bar.close_price)


def _exit_plan(position, bar: DailyBar, trade_date: str, trade_dates: list[str], *, force_liquidate: bool):
    holding_days = _holding_days(position.entry_date, trade_date, trade_dates)
    if position.stop_loss and bar.low_price <= position.stop_loss:
        price = min(position.stop_loss, bar.open_price) if bar.open_price < position.stop_loss else position.stop_loss
        return {"price": price, "reason": "stop_loss", "holding_days": holding_days}
    if position.take_profit and bar.high_price >= position.take_profit:
        price = max(position.take_profit, bar.open_price) if bar.open_price > position.take_profit else position.take_profit
        return {"price": price, "reason": "take_profit", "holding_days": holding_days}
    if holding_days >= max(position.max_holding_days, 1):
        return {"price": bar.close_price, "reason": "max_holding_days", "holding_days": holding_days}
    if force_liquidate:
        return {"price": bar.close_price, "reason": "end_of_backtest", "holding_days": holding_days}
    return None


def _holding_days(entry_date: str, trade_date: str, trade_dates: list[str]) -> int:
    try:
        return trade_dates.index(trade_date) - trade_dates.index(entry_date)
    except ValueError:
        return 0


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


def _config_dict(config: BacktestConfig) -> dict[str, Any]:
    payload = asdict(config)
    payload["signals"] = [
        {
            "signal_date": signal.signal_date,
            "symbol": signal.symbol,
            "strategy_key": signal.strategy_key,
            "score": signal.score,
        }
        for signal in config.signals
    ]
    return payload


def _execution_assumptions(config: BacktestConfig) -> dict[str, Any]:
    """Return user-facing assumptions that materially affect backtest results."""

    return {
        "version": "execution-assumptions-v1",
        "execution_model": config.execution_model,
        "fee_model": {
            "version": "paper_fee_v2",
            "commission": "股票买卖双边按成交额 0.0085% 估算，单笔最低 5 元；ETF/基金类按成交额 0.005% 估算。",
            "stamp_tax": "股票卖出按成交额 0.05% 估算；ETF/基金类不收印花税。",
            "transfer_fee": "股票按成交额 0.001% 估算；ETF/基金类不收过户费。",
            "source": "app.services.paper.fees.calculate_fee",
        },
        "slippage_model": {
            "open": "按当日开盘价撮合。",
            "close": "按当日收盘价撮合。",
            "vwap": "按日线 VWAP 字段撮合；缺失时由数据源决定降级。",
            "entry_zone_touch": "买入使用买点区上沿作为触发价。",
            "conservative_slippage": "买入按 max(open, close)，卖出按 min(open, close)，偏保守估算。",
            "market_impact": "在 conservative_slippage 基础上按成交额参与度追加冲击成本。",
        },
        "same_bar_path": "同一交易日同时触发止损和止盈时先按止损处理；每日先处理退出，再处理新开仓。",
        "price_limit_handling": "撮合前按 A 股涨跌停上下文拒绝不可交易委托；ETF/基金类默认不套用股票涨跌停限制。",
        "suspension_handling": "缺少有效日线、价格为 0 或停牌导致无可用行情时，订单会被拒绝或跳过。",
        "data_quality": "结果同时返回 data_quality 与 attribution.data_quality_summary，用于识别缺失、延迟或降级数据。",
        "position_constraints": {
            "max_position_pct": config.max_position_pct,
            "max_positions": config.max_positions,
            "max_signals_per_day": config.max_signals_per_day,
            "entry_delay_days": config.entry_delay_days,
            "lot_size": config.lot_size,
            "force_liquidate_at_end": config.force_liquidate_at_end,
        },
        "disclaimer": "回测为历史模拟和执行假设结果，不代表未来收益或真实成交承诺。",
    }
