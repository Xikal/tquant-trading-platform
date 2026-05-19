from __future__ import annotations

from dataclasses import asdict
import hashlib
import time
from typing import Any

from app.services.backtest.broker import ExecutionModel
from app.services.backtest.data_provider import BacktestSignal, DailyBar, DailyBarDataProvider


def bars_by_date(histories: dict[str, list[DailyBar]]) -> dict[str, dict[str, DailyBar]]:
    output: dict[str, dict[str, DailyBar]] = {}
    for symbol, bars in histories.items():
        for bar in bars:
            output.setdefault(bar.trade_date, {})[symbol] = bar
    return output


def signals_by_entry_date(
    signals: list[BacktestSignal],
    trade_dates: list[str],
    entry_delay_days: int,
) -> dict[str, list[BacktestSignal]]:
    index_by_date = {trade_date: index for index, trade_date in enumerate(trade_dates)}
    output: dict[str, list[BacktestSignal]] = {}
    delay = max(int(entry_delay_days or 0), 1)
    for signal in signals:
        index = index_by_date.get(signal.signal_date)
        if index is None:
            continue
        entry_index = index + delay
        if entry_index >= len(trade_dates):
            continue
        output.setdefault(trade_dates[entry_index], []).append(signal)
    return output


def dedupe_signals(signals: list[BacktestSignal]) -> list[BacktestSignal]:
    best_by_symbol: dict[str, BacktestSignal] = {}
    for signal in signals:
        current = best_by_symbol.get(signal.symbol)
        if current is None or (signal.score, signal.strategy_key) > (current.score, current.strategy_key):
            best_by_symbol[signal.symbol] = signal
    return sorted(best_by_symbol.values(), key=lambda item: (item.score, item.strategy_key, item.symbol), reverse=True)


def next_trade_dates(trade_dates: list[str]) -> dict[str, str | None]:
    return {
        trade_date: trade_dates[index + 1] if index + 1 < len(trade_dates) else None
        for index, trade_date in enumerate(trade_dates)
    }


def close_prices(bars_for_day: dict[str, DailyBar]) -> dict[str, float]:
    return {symbol: bar.close_price for symbol, bar in bars_for_day.items()}


def normalize_benchmark_symbol(value: str | None) -> str:
    return str(value or "").strip()


def benchmark_curve(
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


def cancel_requested(cancel_token: Any | None) -> bool:
    if cancel_token is None:
        return False
    checker = getattr(cancel_token, "is_cancelled", None)
    if callable(checker):
        return bool(checker())
    return bool(getattr(cancel_token, "cancelled", False))


def timeout_requested(started_monotonic: float, max_duration_seconds: int | float | None) -> bool:
    if max_duration_seconds is None or max_duration_seconds <= 0:
        return False
    return time.monotonic() - started_monotonic >= float(max_duration_seconds)


def dataset_manifest(
    data_provider: DailyBarDataProvider,
    config: Any,
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


def entry_estimated_price(bar: DailyBar, signal: BacktestSignal, execution_model: str) -> float:
    if execution_model in {ExecutionModel.OPEN_PRICE.value, ExecutionModel.NEXT_OPEN.value}:
        return bar.open_price
    if execution_model == ExecutionModel.VWAP.value:
        return bar.vwap
    if execution_model == ExecutionModel.CLOSE_PRICE.value:
        return bar.close_price
    if execution_model == ExecutionModel.ENTRY_ZONE_TOUCH.value and signal.entry_zone_high:
        return signal.entry_zone_high
    return max(bar.open_price, bar.close_price)


def exit_plan(position, bar: DailyBar, trade_date: str, trade_dates: list[str], *, force_liquidate: bool):
    holding_days = holding_days_between(position.entry_date, trade_date, trade_dates)
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


def holding_days_between(entry_date: str, trade_date: str, trade_dates: list[str]) -> int:
    try:
        return trade_dates.index(trade_date) - trade_dates.index(entry_date)
    except ValueError:
        return 0


def config_dict(config: Any) -> dict[str, Any]:
    payload = asdict(config)
    payload["entry_delay_days"] = max(int(payload.get("entry_delay_days") or 0), 1)
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


def execution_assumptions(config: Any) -> dict[str, Any]:
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
            "open": "按入场交易日开盘价作为基准，并追加撮合滑点。",
            "next_open": "信号日后下一个交易日开盘价作为基准，并追加撮合滑点。",
            "close": "按入场交易日收盘价作为基准，并追加撮合滑点；不按收盘价精确成交。",
            "vwap": "按日线 VWAP 字段作为基准；缺失时降级到入场日开盘价，并追加撮合滑点。",
            "entry_zone_touch": "买入使用买点区上沿作为触发价，并追加撮合滑点。",
            "conservative_slippage": "买入按 max(open, close)，卖出按 min(open, close)，再追加撮合滑点，偏保守估算。",
            "market_impact": "在 conservative_slippage 与撮合滑点基础上，按成交额参与度追加冲击成本。",
        },
        "lookahead_guard": "低吸信号默认在信号日后的下一个交易日才允许入场；区间最后一个交易日产生的信号不会被强行同日成交。",
        "same_bar_path": "同一交易日同时触发止损和止盈时先按止损处理；每日先处理退出，再处理新开仓。",
        "price_limit_handling": "撮合前按 A 股涨跌停上下文拒绝不可交易委托；ETF/基金类默认不套用股票涨跌停限制。",
        "suspension_handling": "缺少有效日线、价格为 0 或停牌导致无可用行情时，订单会被拒绝或跳过。",
        "data_quality": "结果同时返回 data_quality 与 attribution.data_quality_summary，用于识别缺失、延迟或降级数据。",
        "position_constraints": {
            "max_position_pct": config.max_position_pct,
            "max_positions": config.max_positions,
            "max_signals_per_day": config.max_signals_per_day,
            "entry_delay_days": max(int(config.entry_delay_days or 0), 1),
            "effective_entry_delay_days": max(int(config.entry_delay_days or 0), 1),
            "lot_size": config.lot_size,
            "force_liquidate_at_end": config.force_liquidate_at_end,
        },
        "disclaimer": "回测为历史模拟和执行假设结果，不代表未来收益或真实成交承诺。",
    }
