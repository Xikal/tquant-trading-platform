from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import DailyBarSnapshot
from app.services.backtest.data_provider import BacktestSignal, DailyBar, DailyBarDataProvider
from app.services.low_buy.strategy_parameter_defaults_parts.runtime import PAPER_DYNAMIC_EXIT_DEFAULTS
from app.services.paper.dynamic_exit import evaluate_paper_exit
from app.services.paper.fees import calculate_fee
from app.services.paper.quote_quality import PaperQuotePrice
from app.services.paper.smart_exit_context import build_exit_context
from app.services.quant.runtime_parameters import get_paper_dynamic_exit


DEFAULT_SMART_T_BACKTEST_STRATEGIES = [
    "first_board",
    "volume_shrink",
    "core_midcap_vwap_ma5_retrace",
    "sector_mainline_first_divergence_low_buy",
]


@dataclass(frozen=True)
class SmartTSignalSample:
    signal_date: str
    washout_date: str
    symbol: str
    name: str
    strategy_key: str
    entry_price: float
    add_price: float
    volume_release_ratio: float
    forward_max_rebound_pct: float
    forward_close_return_pct: float
    net_max_return_pct: float
    success: bool


@dataclass(frozen=True)
class SmartTThresholdStat:
    volume_threshold: float
    sample_count: int
    success_rate_pct: float
    avg_net_max_return_pct: float


@dataclass(frozen=True)
class SmartTBacktestReport:
    start_date: str
    end_date: str
    strategies: list[str]
    signal_count: int
    washout_signal_count: int
    success_rate_pct: float
    avg_forward_max_rebound_pct: float
    avg_forward_close_return_pct: float
    avg_net_max_return_pct: float
    expected_rebound_pct: float
    min_net_profit_pct: float
    forward_days: int
    threshold_stats: list[SmartTThresholdStat] = field(default_factory=list)
    samples: list[SmartTSignalSample] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


class SmartTBacktestService:
    """Historical validation for SmartT washout add signals.

    This is read-only research logic. It does not alter paper-trading orders.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.provider = DailyBarDataProvider(db)

    def run(
        self,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        strategies: list[str] | None = None,
        max_signals_per_day: int = 20,
        forward_days: int = 3,
        context_lookback: int = 23,
        sample_limit: int = 50,
    ) -> SmartTBacktestReport:
        start, end = self._date_range(start_date=start_date, end_date=end_date)
        strategy_keys = [item for item in (strategies or DEFAULT_SMART_T_BACKTEST_STRATEGIES) if item]
        signals = self.provider.load_low_buy_signals(
            strategies=strategy_keys,
            start_date=start,
            end_date=end,
            max_signals_per_day=max_signals_per_day,
        )
        histories = self.provider.fetch_bars(
            {signal.symbol for signal in signals},
            start_date=start,
            end_date=end,
        )
        params = _dynamic_params()
        expected_rebound = _float_param(params, "smart_t_expected_rebound_pct", 1.2)
        min_net = _float_param(params, "min_net_profit_pct", 0.6)
        samples = collect_smart_t_washout_samples(
            signals=signals,
            histories=histories,
            params=params,
            expected_rebound_pct=expected_rebound,
            min_net_profit_pct=min_net,
            forward_days=max(forward_days, 1),
            context_lookback=max(context_lookback, 8),
        )
        return _report(
            start_date=start,
            end_date=end,
            strategies=strategy_keys,
            signal_count=len(signals),
            samples=samples,
            expected_rebound_pct=expected_rebound,
            min_net_profit_pct=min_net,
            forward_days=max(forward_days, 1),
            sample_limit=sample_limit,
        )

    def _date_range(self, *, start_date: str | None, end_date: str | None) -> tuple[str, str]:
        if start_date and end_date:
            return start_date, end_date
        rows = (
            self.db.execute(
                select(DailyBarSnapshot.trade_date)
                .distinct()
                .order_by(DailyBarSnapshot.trade_date.desc())
                .limit(180)
            )
            .scalars()
            .all()
        )
        dates = sorted(str(item) for item in rows)
        if not dates:
            fallback = datetime.now().date().isoformat()
            return start_date or fallback, end_date or fallback
        return start_date or dates[0], end_date or dates[-1]


def collect_smart_t_washout_samples(
    *,
    signals: list[BacktestSignal],
    histories: dict[str, list[DailyBar]],
    params: dict[str, Any],
    expected_rebound_pct: float,
    min_net_profit_pct: float,
    forward_days: int,
    context_lookback: int,
) -> list[SmartTSignalSample]:
    samples: list[SmartTSignalSample] = []
    for signal in signals:
        bars = histories.get(signal.symbol, [])
        index_by_date = {bar.trade_date: index for index, bar in enumerate(bars)}
        signal_index = index_by_date.get(signal.signal_date)
        if signal_index is None:
            continue
        entry_bar = bars[signal_index]
        if entry_bar.close_price <= 0:
            continue
        start_index = signal_index + 1
        end_index = min(len(bars) - forward_days, signal_index + max(signal.max_holding_days, 1) + 1)
        for washout_index in range(start_index, max(start_index, end_index)):
            washout_bar = bars[washout_index]
            context_bars = [_bar_adapter(item) for item in bars[max(0, washout_index - context_lookback + 1): washout_index + 1]]
            context = build_exit_context(_quote(signal.symbol, washout_bar), context_bars)
            row = _position(signal, entry_price=entry_bar.close_price)
            decision = evaluate_paper_exit(row, price=washout_bar.close_price, now=_date_time(washout_bar.trade_date), context=context)
            if decision.action_signal != "washout":
                continue
            samples.append(
                _sample(
                    signal=signal,
                    entry_bar=entry_bar,
                    washout_bar=washout_bar,
                    future_bars=bars[washout_index + 1: washout_index + 1 + forward_days],
                    volume_release_ratio=context.volume_release_ratio,
                    expected_rebound_pct=expected_rebound_pct,
                    min_net_profit_pct=min_net_profit_pct,
                )
            )
            break
    return samples


def _sample(
    *,
    signal: BacktestSignal,
    entry_bar: DailyBar,
    washout_bar: DailyBar,
    future_bars: list[DailyBar],
    volume_release_ratio: float,
    expected_rebound_pct: float,
    min_net_profit_pct: float,
) -> SmartTSignalSample:
    add_price = washout_bar.close_price
    future_high = max((bar.high_price for bar in future_bars if bar.high_price > 0), default=add_price)
    future_close = future_bars[-1].close_price if future_bars else add_price
    max_rebound = _return_pct(future_high, add_price)
    close_return = _return_pct(future_close, add_price)
    fee_drag = _round_trip_fee_drag_pct(symbol=signal.symbol, price=add_price, quantity=1000, rebound_pct=expected_rebound_pct)
    net_max = max_rebound - fee_drag
    return SmartTSignalSample(
        signal_date=signal.signal_date,
        washout_date=washout_bar.trade_date,
        symbol=signal.symbol,
        name=signal.name,
        strategy_key=signal.strategy_key,
        entry_price=round(entry_bar.close_price, 4),
        add_price=round(add_price, 4),
        volume_release_ratio=round(volume_release_ratio, 4),
        forward_max_rebound_pct=round(max_rebound, 4),
        forward_close_return_pct=round(close_return, 4),
        net_max_return_pct=round(net_max, 4),
        success=net_max >= min_net_profit_pct,
    )


def _report(
    *,
    start_date: str,
    end_date: str,
    strategies: list[str],
    signal_count: int,
    samples: list[SmartTSignalSample],
    expected_rebound_pct: float,
    min_net_profit_pct: float,
    forward_days: int,
    sample_limit: int,
) -> SmartTBacktestReport:
    notes: list[str] = []
    if not samples:
        notes.append("历史样本中未触发 SmartT 洗盘加仓信号；请扩大时间范围或检查分钟/日线数据质量。")
    else:
        notes.append("当前为日线代理验证；真实盘中分钟级回测仍需更细分时数据。")
    return SmartTBacktestReport(
        start_date=start_date,
        end_date=end_date,
        strategies=strategies,
        signal_count=signal_count,
        washout_signal_count=len(samples),
        success_rate_pct=_rate(sum(1 for item in samples if item.success), len(samples)),
        avg_forward_max_rebound_pct=_avg(item.forward_max_rebound_pct for item in samples),
        avg_forward_close_return_pct=_avg(item.forward_close_return_pct for item in samples),
        avg_net_max_return_pct=_avg(item.net_max_return_pct for item in samples),
        expected_rebound_pct=round(expected_rebound_pct, 4),
        min_net_profit_pct=round(min_net_profit_pct, 4),
        forward_days=forward_days,
        threshold_stats=_threshold_stats(samples),
        samples=samples[: max(sample_limit, 0)],
        notes=notes,
    )


def _threshold_stats(samples: list[SmartTSignalSample]) -> list[SmartTThresholdStat]:
    output: list[SmartTThresholdStat] = []
    for threshold in (0.6, 0.7, 0.8, 0.85, 0.9, 1.0):
        selected = [item for item in samples if item.volume_release_ratio <= threshold]
        output.append(
            SmartTThresholdStat(
                volume_threshold=threshold,
                sample_count=len(selected),
                success_rate_pct=_rate(sum(1 for item in selected if item.success), len(selected)),
                avg_net_max_return_pct=_avg(item.net_max_return_pct for item in selected),
            )
        )
    return output


def _position(signal: BacktestSignal, *, entry_price: float) -> SimpleNamespace:
    return SimpleNamespace(
        symbol=signal.symbol,
        name=signal.name,
        available_quantity=1000,
        cost_basis=entry_price,
        opened_at=_date_time(signal.signal_date),
        strategy_sources=f'["{signal.strategy_key}"]',
    )


def _quote(symbol: str, bar: DailyBar) -> PaperQuotePrice:
    return PaperQuotePrice(
        symbol=symbol,
        price=bar.close_price,
        quality="estimated",
        source="daily_bar_proxy",
        open_price=bar.open_price,
        high_price=bar.high_price,
        low_price=bar.low_price,
        prev_close=bar.pre_close,
        change_pct=bar.pct_chg,
    )


def _bar_adapter(bar: DailyBar) -> SimpleNamespace:
    return SimpleNamespace(
        open=bar.open_price,
        close=bar.close_price,
        high=bar.high_price,
        low=bar.low_price,
        volume=bar.volume,
        amount=bar.amount,
    )


def _round_trip_fee_drag_pct(*, symbol: str, price: float, quantity: int, rebound_pct: float) -> float:
    if price <= 0 or quantity <= 0:
        return 0.0
    buy_fee = calculate_fee(symbol=symbol, side="buy", price=Decimal(str(price)), quantity=quantity)
    sell_price = price * (1 + rebound_pct / 100)
    sell_fee = calculate_fee(symbol=symbol, side="sell", price=Decimal(str(sell_price)), quantity=quantity)
    gross = price * quantity
    return float(buy_fee.total_fee + sell_fee.total_fee) / gross * 100 if gross > 0 else 0.0


def _dynamic_params() -> dict[str, Any]:
    values = get_paper_dynamic_exit()
    return {**PAPER_DYNAMIC_EXIT_DEFAULTS, **values} if isinstance(values, dict) else dict(PAPER_DYNAMIC_EXIT_DEFAULTS)


def _date_time(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d")


def _return_pct(value: float, base: float) -> float:
    return (value - base) / base * 100 if base > 0 else 0.0


def _float_param(params: dict[str, Any], key: str, fallback: float) -> float:
    try:
        return float(params.get(key, fallback))
    except (TypeError, ValueError):
        return float(fallback)


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator * 100, 2) if denominator > 0 else 0.0


def _avg(values: Any) -> float:
    items = [float(item) for item in values]
    return round(sum(items) / len(items), 4) if items else 0.0
