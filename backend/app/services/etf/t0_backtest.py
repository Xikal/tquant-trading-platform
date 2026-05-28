from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from app.models.schemas import KlineBar
from app.services.etf.t0_signal import EtfT0SignalParams, evaluate_etf_t0_signal
from app.services.etf.universe import etf_profile_for
from app.services.paper.fees import calculate_fee


ETF_T0_BACKTEST_VERSION = "etf-t0-backtest-v1"
ETF_T0_RESEARCH_VERSION = "etf-t0-research-v1"
DEFAULT_MARKET_REGIMES = ("牛市", "震荡", "熊市", "退潮", "强反弹")


@dataclass(frozen=True)
class EtfT0BacktestTrade:
    symbol: str
    side: str
    entry_time: str
    exit_time: str
    entry_price: float
    exit_price: float
    quantity: int
    gross_pnl: float
    total_fee: float
    net_pnl: float
    net_return_pct: float
    exit_reason: str
    signal_snapshot: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EtfT0BacktestReport:
    symbol: str
    name: str
    version: str
    bar_count: int
    trade_count: int
    win_rate_pct: float
    gross_pnl: float
    net_pnl: float
    avg_net_return_pct: float
    profit_factor: float | None
    max_drawdown_pct: float
    baseline_hold_return_pct: float
    baseline_no_trade_return_pct: float
    turnover: float
    rejected_signal_count: int
    trades: list[EtfT0BacktestTrade] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "version": self.version,
            "bar_count": self.bar_count,
            "trade_count": self.trade_count,
            "win_rate_pct": self.win_rate_pct,
            "gross_pnl": self.gross_pnl,
            "net_pnl": self.net_pnl,
            "avg_net_return_pct": self.avg_net_return_pct,
            "profit_factor": self.profit_factor,
            "max_drawdown_pct": self.max_drawdown_pct,
            "baseline_hold_return_pct": self.baseline_hold_return_pct,
            "baseline_no_trade_return_pct": self.baseline_no_trade_return_pct,
            "turnover": self.turnover,
            "rejected_signal_count": self.rejected_signal_count,
            "trades": [trade.__dict__ for trade in self.trades],
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class EtfT0HeatmapCell:
    buy_vwap_deviation_pct: float
    sell_vwap_deviation_pct: float
    oversold_rsi: float
    overbought_rsi: float
    trade_count: int
    win_rate_pct: float
    net_pnl: float
    profit_factor: float | None
    max_drawdown_pct: float
    baseline_hold_return_pct: float
    score: float
    pass_gate: bool
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "buy_vwap_deviation_pct": self.buy_vwap_deviation_pct,
            "sell_vwap_deviation_pct": self.sell_vwap_deviation_pct,
            "oversold_rsi": self.oversold_rsi,
            "overbought_rsi": self.overbought_rsi,
            "trade_count": self.trade_count,
            "win_rate_pct": self.win_rate_pct,
            "net_pnl": self.net_pnl,
            "profit_factor": self.profit_factor,
            "max_drawdown_pct": self.max_drawdown_pct,
            "baseline_hold_return_pct": self.baseline_hold_return_pct,
            "score": self.score,
            "pass_gate": self.pass_gate,
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class EtfT0MarketRegimeSegment:
    regime: str
    start_time: str
    end_time: str


@dataclass(frozen=True)
class EtfT0RegimeValidation:
    regime: str
    start_time: str
    end_time: str
    bar_count: int
    trade_count: int
    win_rate_pct: float
    net_pnl: float
    profit_factor: float | None
    max_drawdown_pct: float
    baseline_hold_return_pct: float
    verdict: str
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "regime": self.regime,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "bar_count": self.bar_count,
            "trade_count": self.trade_count,
            "win_rate_pct": self.win_rate_pct,
            "net_pnl": self.net_pnl,
            "profit_factor": self.profit_factor,
            "max_drawdown_pct": self.max_drawdown_pct,
            "baseline_hold_return_pct": self.baseline_hold_return_pct,
            "verdict": self.verdict,
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class EtfT0ResearchReport:
    symbol: str
    name: str
    version: str
    research_only: bool
    base_report: EtfT0BacktestReport
    heatmap: list[EtfT0HeatmapCell] = field(default_factory=list)
    regime_validations: list[EtfT0RegimeValidation] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "version": self.version,
            "research_only": self.research_only,
            "base_report": self.base_report.to_dict(),
            "heatmap": [item.to_dict() for item in self.heatmap],
            "regime_validations": [item.to_dict() for item in self.regime_validations],
            "notes": list(self.notes),
        }


def run_etf_t0_backtest(
    *,
    symbol: str,
    name: str = "",
    bars: list[KlineBar],
    quantity: int = 10_000,
    min_signal_bars: int = 20,
    max_trades_per_day: int = 3,
    params: dict[str, Any] | EtfT0SignalParams | None = None,
) -> EtfT0BacktestReport:
    clean_bars = _clean_bars(bars)
    profile = etf_profile_for(symbol, name=name, instrument_type="fund")
    display_name = name or (profile.name if profile is not None else symbol)
    if profile is None or not profile.same_day_sell_allowed:
        return _empty_report(
            symbol=symbol,
            name=display_name,
            bars=clean_bars,
            notes=["ETF universe 未放行 T+0，回测不生成交易。"],
        )
    if len(clean_bars) < max(min_signal_bars, 2):
        return _empty_report(
            symbol=profile.symbol,
            name=display_name,
            bars=clean_bars,
            notes=["分钟样本不足，回测不生成交易。"],
        )
    round_lot_quantity = max(100, int(quantity // 100 * 100))
    max_trades = max(0, int(max_trades_per_day))
    trades: list[EtfT0BacktestTrade] = []
    rejected = 0
    index = max(2, min_signal_bars)
    while index < len(clean_bars) - 1 and len(trades) < max_trades:
        window = clean_bars[: index + 1]
        signal = evaluate_etf_t0_signal(
            symbol=profile.symbol,
            name=display_name,
            bars=window,
            params=params,
        )
        if signal.action not in {"positive_t_buy", "negative_t_sell"}:
            if signal.risk_flags:
                rejected += 1
            index += 1
            continue
        exit_index, exit_reason = _find_exit(
            action=signal.action,
            bars=clean_bars,
            start_index=index + 1,
            target_price=signal.target_price,
            stop_price=signal.stop_price,
        )
        if exit_index <= index:
            rejected += 1
            index += 1
            continue
        trade = _build_trade(
            symbol=profile.symbol,
            action=signal.action,
            entry_bar=clean_bars[index],
            exit_bar=clean_bars[exit_index],
            quantity=round_lot_quantity,
            exit_reason=exit_reason,
            signal_snapshot=signal.to_dict(),
        )
        trades.append(trade)
        index = exit_index + 1
    return _report(symbol=profile.symbol, name=display_name, bars=clean_bars, trades=trades, rejected=rejected)


def run_etf_t0_research_report(
    *,
    symbol: str,
    name: str = "",
    bars: list[KlineBar],
    quantity: int = 10_000,
    min_signal_bars: int = 20,
    max_trades_per_day: int = 3,
    params: dict[str, Any] | EtfT0SignalParams | None = None,
    vwap_deviation_values: list[float] | None = None,
    oversold_rsi_values: list[float] | None = None,
    market_regime_segments: list[EtfT0MarketRegimeSegment] | None = None,
) -> EtfT0ResearchReport:
    clean_bars = _clean_bars(bars)
    base_report = run_etf_t0_backtest(
        symbol=symbol,
        name=name,
        bars=clean_bars,
        quantity=quantity,
        min_signal_bars=min_signal_bars,
        max_trades_per_day=max_trades_per_day,
        params=params,
    )
    heatmap = _build_heatmap(
        symbol=symbol,
        name=base_report.name,
        bars=clean_bars,
        quantity=quantity,
        min_signal_bars=min_signal_bars,
        max_trades_per_day=max_trades_per_day,
        params=params,
        vwap_deviation_values=vwap_deviation_values,
        oversold_rsi_values=oversold_rsi_values,
    )
    regime_validations = _build_regime_validations(
        symbol=symbol,
        name=base_report.name,
        bars=clean_bars,
        quantity=quantity,
        min_signal_bars=min_signal_bars,
        max_trades_per_day=max_trades_per_day,
        params=params,
        market_regime_segments=market_regime_segments,
    )
    notes = [
        "ETF T0 参数热力图和五类市场状态验证仅用于研究验收，不自动提升为生产参数。",
        "策略真源仍为 Python；Go 只读行情快照，Rust 只做指标加速和 parity 验收。",
    ]
    if not clean_bars:
        notes.append("分钟线为空，热力图和市场状态验证只返回空报告。")
    return EtfT0ResearchReport(
        symbol=base_report.symbol,
        name=base_report.name,
        version=ETF_T0_RESEARCH_VERSION,
        research_only=True,
        base_report=base_report,
        heatmap=heatmap,
        regime_validations=regime_validations,
        notes=notes,
    )


def _find_exit(
    *,
    action: str,
    bars: list[KlineBar],
    start_index: int,
    target_price: float,
    stop_price: float,
    max_hold_bars: int = 30,
) -> tuple[int, str]:
    last_index = min(len(bars) - 1, start_index + max(1, max_hold_bars) - 1)
    for index in range(start_index, last_index + 1):
        bar = bars[index]
        close = float(bar.close)
        if action == "positive_t_buy":
            if close >= target_price > 0:
                return index, "target_reached"
            if close <= stop_price < target_price:
                return index, "stop_loss"
        if action == "negative_t_sell":
            if close <= target_price < stop_price:
                return index, "target_reached"
            if close >= stop_price > target_price:
                return index, "stop_loss"
    return last_index, "time_exit"


def _build_heatmap(
    *,
    symbol: str,
    name: str,
    bars: list[KlineBar],
    quantity: int,
    min_signal_bars: int,
    max_trades_per_day: int,
    params: dict[str, Any] | EtfT0SignalParams | None,
    vwap_deviation_values: list[float] | None,
    oversold_rsi_values: list[float] | None,
) -> list[EtfT0HeatmapCell]:
    if len(bars) < max(min_signal_bars, 2):
        return []
    base_params = _params_dict(params)
    deviations = _bounded_float_grid(vwap_deviation_values, fallback=[0.25, 0.35, 0.45], low=0.05, high=5.0)
    oversold_values = _bounded_float_grid(oversold_rsi_values, fallback=[34.0, 38.0, 42.0], low=10.0, high=60.0)
    cells: list[EtfT0HeatmapCell] = []
    for deviation in deviations:
        for oversold in oversold_values:
            overbought = max(55.0, min(90.0, 100.0 - oversold))
            cell_params = {
                **base_params,
                "signal_buy_vwap_deviation_pct": deviation,
                "signal_sell_vwap_deviation_pct": deviation,
                "signal_oversold_rsi": oversold,
                "signal_overbought_rsi": overbought,
            }
            report = run_etf_t0_backtest(
                symbol=symbol,
                name=name,
                bars=bars,
                quantity=quantity,
                min_signal_bars=min_signal_bars,
                max_trades_per_day=max_trades_per_day,
                params=cell_params,
            )
            score = _heatmap_score(report)
            pass_gate = _passes_research_gate(report)
            notes = [
                "通过基础研究门槛" if pass_gate else "未通过基础研究门槛",
                "仍需样本外、滑点敏感性和模拟盘观察确认。",
            ]
            cells.append(
                EtfT0HeatmapCell(
                    buy_vwap_deviation_pct=round(deviation, 4),
                    sell_vwap_deviation_pct=round(deviation, 4),
                    oversold_rsi=round(oversold, 4),
                    overbought_rsi=round(overbought, 4),
                    trade_count=report.trade_count,
                    win_rate_pct=report.win_rate_pct,
                    net_pnl=report.net_pnl,
                    profit_factor=report.profit_factor,
                    max_drawdown_pct=report.max_drawdown_pct,
                    baseline_hold_return_pct=report.baseline_hold_return_pct,
                    score=score,
                    pass_gate=pass_gate,
                    notes=notes,
                )
            )
    return sorted(cells, key=lambda item: (item.pass_gate, item.score, item.net_pnl), reverse=True)


def _build_regime_validations(
    *,
    symbol: str,
    name: str,
    bars: list[KlineBar],
    quantity: int,
    min_signal_bars: int,
    max_trades_per_day: int,
    params: dict[str, Any] | EtfT0SignalParams | None,
    market_regime_segments: list[EtfT0MarketRegimeSegment] | None,
) -> list[EtfT0RegimeValidation]:
    if not bars:
        return []
    segments = market_regime_segments or _default_regime_segments(bars)
    result: list[EtfT0RegimeValidation] = []
    for segment in segments:
        segment_bars = _bars_in_segment(bars, segment)
        report = run_etf_t0_backtest(
            symbol=symbol,
            name=name,
            bars=segment_bars,
            quantity=quantity,
            min_signal_bars=min(min_signal_bars, max(5, len(segment_bars) // 2)) if segment_bars else min_signal_bars,
            max_trades_per_day=max_trades_per_day,
            params=params,
        )
        verdict, notes = _regime_verdict(report)
        result.append(
            EtfT0RegimeValidation(
                regime=segment.regime,
                start_time=segment.start_time,
                end_time=segment.end_time,
                bar_count=report.bar_count,
                trade_count=report.trade_count,
                win_rate_pct=report.win_rate_pct,
                net_pnl=report.net_pnl,
                profit_factor=report.profit_factor,
                max_drawdown_pct=report.max_drawdown_pct,
                baseline_hold_return_pct=report.baseline_hold_return_pct,
                verdict=verdict,
                notes=notes,
            )
        )
    return result


def _default_regime_segments(bars: list[KlineBar]) -> list[EtfT0MarketRegimeSegment]:
    if not bars:
        return []
    size = max(1, len(bars) // len(DEFAULT_MARKET_REGIMES))
    segments: list[EtfT0MarketRegimeSegment] = []
    for index, regime in enumerate(DEFAULT_MARKET_REGIMES):
        start = min(index * size, len(bars) - 1)
        end = len(bars) - 1 if index == len(DEFAULT_MARKET_REGIMES) - 1 else min((index + 1) * size - 1, len(bars) - 1)
        segments.append(
            EtfT0MarketRegimeSegment(
                regime=regime,
                start_time=str(bars[start].timestamp),
                end_time=str(bars[end].timestamp),
            )
        )
    return segments


def _bars_in_segment(bars: list[KlineBar], segment: EtfT0MarketRegimeSegment) -> list[KlineBar]:
    start = str(segment.start_time or "")
    end = str(segment.end_time or "")
    return [bar for bar in bars if (not start or str(bar.timestamp) >= start) and (not end or str(bar.timestamp) <= end)]


def _regime_verdict(report: EtfT0BacktestReport) -> tuple[str, list[str]]:
    if report.bar_count == 0:
        return "needs_data", ["该市场状态没有分钟样本，不能验收。"]
    if report.trade_count == 0:
        return "observe", ["该市场状态未产生交易，保持观察，不作为生产放行证据。"]
    if report.net_pnl < 0 and report.max_drawdown_pct <= -20:
        return "fail", ["净收益为负且回撤过深，必须下调参数或禁用该状态。"]
    if report.net_pnl >= 0 and report.max_drawdown_pct > -20:
        return "pass", ["样本内满足基础门槛，仍需独立样本外和模拟盘观察。"]
    return "caution", ["表现不稳定，不能直接进入生产参数。"]


def _heatmap_score(report: EtfT0BacktestReport) -> float:
    pf = float(report.profit_factor or 1.0)
    drawdown_penalty = abs(min(report.max_drawdown_pct, 0.0)) * 0.2
    trade_bonus = min(report.trade_count, 5) * 0.5
    baseline_gap = report.net_pnl - max(report.baseline_hold_return_pct, 0.0)
    return round(report.net_pnl + pf * 10 + trade_bonus - drawdown_penalty + baseline_gap * 0.1, 4)


def _passes_research_gate(report: EtfT0BacktestReport) -> bool:
    if report.trade_count <= 0:
        return False
    if report.net_pnl < 0:
        return False
    if report.max_drawdown_pct <= -35:
        return False
    if report.profit_factor is not None and report.profit_factor < 1.0:
        return False
    return True


def _params_dict(params: dict[str, Any] | EtfT0SignalParams | None) -> dict[str, Any]:
    if params is None:
        return {}
    if isinstance(params, dict):
        return dict(params)
    return {
        "signal_min_bars": params.min_bars,
        "signal_bollinger_window": params.bollinger_window,
        "signal_bollinger_std": params.bollinger_std,
        "signal_rsi_period": params.rsi_period,
        "signal_buy_vwap_deviation_pct": params.buy_vwap_deviation_pct,
        "signal_sell_vwap_deviation_pct": params.sell_vwap_deviation_pct,
        "signal_min_net_edge_pct": params.min_net_edge_pct,
        "signal_oversold_rsi": params.oversold_rsi,
        "signal_overbought_rsi": params.overbought_rsi,
        "signal_max_volume_ratio": params.max_volume_ratio,
        "signal_min_volume_ratio": params.min_volume_ratio,
        "signal_max_trend_slope_abs_pct": params.max_trend_slope_abs_pct,
        "signal_stop_loss_pct": params.stop_loss_pct,
        "signal_target_buffer_pct": params.target_buffer_pct,
        "signal_liquidity_intraday_amount_ratio": params.liquidity_intraday_amount_ratio,
        "signal_tracking_divergence_block_pct": params.tracking_divergence_block_pct,
    }


def _bounded_float_grid(values: list[float] | None, *, fallback: list[float], low: float, high: float) -> list[float]:
    raw_values = values if values else fallback
    result: list[float] = []
    for value in raw_values[:8]:
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if low <= number <= high and number not in result:
            result.append(number)
    return result or list(fallback)


def _build_trade(
    *,
    symbol: str,
    action: str,
    entry_bar: KlineBar,
    exit_bar: KlineBar,
    quantity: int,
    exit_reason: str,
    signal_snapshot: dict[str, Any],
) -> EtfT0BacktestTrade:
    entry = float(entry_bar.close)
    exit_price = float(exit_bar.close)
    if action == "positive_t_buy":
        buy_price, sell_price = entry, exit_price
        side = "positive_t"
        gross_pnl = (sell_price - buy_price) * quantity
    else:
        sell_price, buy_price = entry, exit_price
        side = "negative_t"
        gross_pnl = (sell_price - buy_price) * quantity
    buy_fee = calculate_fee(symbol=symbol, side="buy", price=Decimal(str(buy_price)), quantity=quantity)
    sell_fee = calculate_fee(symbol=symbol, side="sell", price=Decimal(str(sell_price)), quantity=quantity)
    total_fee = float(buy_fee.total_fee + sell_fee.total_fee)
    gross_amount = entry * quantity
    net_pnl = gross_pnl - total_fee
    net_return = (net_pnl / gross_amount * 100) if gross_amount > 0 else 0.0
    return EtfT0BacktestTrade(
        symbol=symbol,
        side=side,
        entry_time=str(entry_bar.timestamp),
        exit_time=str(exit_bar.timestamp),
        entry_price=round(entry, 4),
        exit_price=round(exit_price, 4),
        quantity=quantity,
        gross_pnl=round(gross_pnl, 2),
        total_fee=round(total_fee, 2),
        net_pnl=round(net_pnl, 2),
        net_return_pct=round(net_return, 4),
        exit_reason=exit_reason,
        signal_snapshot=signal_snapshot,
    )


def _report(
    *,
    symbol: str,
    name: str,
    bars: list[KlineBar],
    trades: list[EtfT0BacktestTrade],
    rejected: int,
) -> EtfT0BacktestReport:
    wins = [trade for trade in trades if trade.net_pnl > 0]
    losses = [trade for trade in trades if trade.net_pnl < 0]
    gross_pnl = sum(trade.gross_pnl for trade in trades)
    net_pnl = sum(trade.net_pnl for trade in trades)
    gross_profit = sum(trade.net_pnl for trade in wins)
    gross_loss = abs(sum(trade.net_pnl for trade in losses))
    profit_factor = round(gross_profit / gross_loss, 4) if gross_loss > 0 else None
    return EtfT0BacktestReport(
        symbol=symbol,
        name=name,
        version=ETF_T0_BACKTEST_VERSION,
        bar_count=len(bars),
        trade_count=len(trades),
        win_rate_pct=_rate(len(wins), len(trades)),
        gross_pnl=round(gross_pnl, 2),
        net_pnl=round(net_pnl, 2),
        avg_net_return_pct=round(sum(trade.net_return_pct for trade in trades) / max(len(trades), 1), 4),
        profit_factor=profit_factor,
        max_drawdown_pct=_max_drawdown_pct([trade.net_pnl for trade in trades]),
        baseline_hold_return_pct=_baseline_hold_return_pct(bars),
        baseline_no_trade_return_pct=0.0,
        turnover=round(sum(trade.entry_price * trade.quantity for trade in trades), 2),
        rejected_signal_count=rejected,
        trades=trades,
        notes=["分钟级 ETF T0 回测仅用于研究验收，不写模拟盘账本。"],
    )


def _empty_report(*, symbol: str, name: str, bars: list[KlineBar], notes: list[str]) -> EtfT0BacktestReport:
    return EtfT0BacktestReport(
        symbol=symbol,
        name=name,
        version=ETF_T0_BACKTEST_VERSION,
        bar_count=len(bars),
        trade_count=0,
        win_rate_pct=0.0,
        gross_pnl=0.0,
        net_pnl=0.0,
        avg_net_return_pct=0.0,
        profit_factor=None,
        max_drawdown_pct=0.0,
        baseline_hold_return_pct=_baseline_hold_return_pct(bars),
        baseline_no_trade_return_pct=0.0,
        turnover=0.0,
        rejected_signal_count=0,
        notes=notes,
    )


def _clean_bars(bars: list[KlineBar]) -> list[KlineBar]:
    return sorted(
        [
            bar
            for bar in bars
            if float(getattr(bar, "close", 0) or 0) > 0
            and float(getattr(bar, "high", 0) or 0) > 0
            and float(getattr(bar, "low", 0) or 0) > 0
        ],
        key=lambda item: str(getattr(item, "timestamp", "") or ""),
    )


def _baseline_hold_return_pct(bars: list[KlineBar]) -> float:
    if len(bars) < 2 or float(bars[0].close or 0) <= 0:
        return 0.0
    return round((float(bars[-1].close) / float(bars[0].close) - 1.0) * 100, 4)


def _max_drawdown_pct(pnl_values: list[float]) -> float:
    equity = 0.0
    peak = 0.0
    drawdown = 0.0
    for pnl in pnl_values:
        equity += pnl
        peak = max(peak, equity)
        drawdown = min(drawdown, equity - peak)
    base = max(abs(peak), 1.0)
    return round(drawdown / base * 100, 4)


def _rate(part: int, total: int) -> float:
    return round(part / total * 100, 4) if total else 0.0
