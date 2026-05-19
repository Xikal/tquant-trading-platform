from __future__ import annotations

import random
from dataclasses import asdict, dataclass, replace
from itertools import product
from typing import Any, Callable

from app.models.schema_defs.backtest import ALLOWED_OPTIMIZATION_PARAMS
from app.services.backtest.data_provider import BacktestSignal, DailyBar
from app.services.backtest.engine import BacktestConfig, BacktestEngine, BacktestResult


TARGET_METRIC_KEYS = {
    "sharpe": "sharpe_ratio",
    "total_return_pct": "total_return_pct",
    "profit_factor": "profit_factor",
    "win_rate_pct": "win_rate_pct",
}


@dataclass(frozen=True)
class OptimizationCandidate:
    params: dict[str, Any]
    score: float
    metrics: dict[str, Any]
    period: str = "is"
    rank: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OptimizationReport:
    candidates: list[OptimizationCandidate]
    best_is: OptimizationCandidate | None
    best_oos: OptimizationCandidate | None
    oos_downgrade: bool
    sampled: bool
    combination_count: int
    evaluated_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "validation_protocol": "mandatory_is_oos_split",
            "oos_required": True,
            "candidates": [item.to_dict() for item in self.candidates],
            "best_is": self.best_is.to_dict() if self.best_is is not None else None,
            "best_oos": self.best_oos.to_dict() if self.best_oos is not None else None,
            "oos_downgrade": self.oos_downgrade,
            "sampled": self.sampled,
            "combination_count": self.combination_count,
            "evaluated_count": self.evaluated_count,
            "auto_apply": False,
        }


ProgressCallback = Callable[[float, str], None]


@dataclass(frozen=True)
class _RangeData:
    config: BacktestConfig
    trade_dates: list[str]
    histories: dict[str, list[DailyBar]]


class BacktestOptimizer:
    """Bounded parameter search with mandatory out-of-sample validation."""

    def __init__(self, engine: BacktestEngine) -> None:
        self.engine = engine

    def optimize_with_oos(
        self,
        base_config: BacktestConfig,
        *,
        param_grid: dict[str, list[Any]],
        train_start: str,
        train_end: str,
        test_start: str,
        test_end: str,
        max_combinations: int = 500,
        score_key: str = "sharpe",
        cancel_token: Any | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> OptimizationReport:
        _validate_oos_ranges(train_start, train_end, test_start, test_end)
        param_sets, total_count, sampled = enumerate_param_sets(param_grid, max_combinations=max_combinations)
        train_data = _prepare_range_data(self.engine, base_config, train_start, train_end)
        candidates = self.evaluate_param_sets(
            train_data.config,
            param_sets=param_sets,
            start_date=train_start,
            end_date=train_end,
            score_key=score_key,
            period="is",
            cancel_token=cancel_token,
            progress_callback=progress_callback,
            progress_start=0.0,
            progress_end=85.0,
            histories=train_data.histories,
            trade_dates=train_data.trade_dates,
        )
        best_is = candidates[0] if candidates else None
        best_oos = None
        oos_downgrade = False
        if best_is is not None and not _cancel_requested(cancel_token):
            test_data = _prepare_range_data(self.engine, base_config, test_start, test_end)
            result = self.run_params(
                test_data.config,
                params=best_is.params,
                start_date=test_start,
                end_date=test_end,
                cancel_token=cancel_token,
                histories=test_data.histories,
                trade_dates=test_data.trade_dates,
            )
            best_oos = _candidate_or_none(
                params=best_is.params,
                result=result,
                score_key=score_key,
                period="oos",
                rank=1,
            )
            oos_downgrade = best_oos is None or _is_oos_downgrade(best_is.metrics, best_oos.metrics)
            if progress_callback is not None:
                progress_callback(95.0, "样本外验证完成")
        return OptimizationReport(
            candidates=candidates,
            best_is=best_is,
            best_oos=best_oos,
            oos_downgrade=oos_downgrade,
            sampled=sampled,
            combination_count=total_count,
            evaluated_count=len(candidates),
        )

    def evaluate_param_sets(
        self,
        base_config: BacktestConfig,
        *,
        param_sets: list[dict[str, Any]],
        start_date: str,
        end_date: str,
        score_key: str = "sharpe",
        period: str = "is",
        cancel_token: Any | None = None,
        progress_callback: ProgressCallback | None = None,
        progress_start: float = 0.0,
        progress_end: float = 100.0,
        histories: dict[str, list[DailyBar]] | None = None,
        trade_dates: list[str] | None = None,
    ) -> list[OptimizationCandidate]:
        range_data = (
            _RangeData(config=base_config, trade_dates=list(trade_dates), histories=histories)
            if histories is not None and trade_dates is not None
            else _prepare_range_data(self.engine, base_config, start_date, end_date)
        )
        candidates: list[OptimizationCandidate] = []
        total = max(len(param_sets), 1)
        for index, params in enumerate(param_sets):
            if _cancel_requested(cancel_token):
                break
            result = self.run_params(
                range_data.config,
                params=params,
                start_date=start_date,
                end_date=end_date,
                cancel_token=cancel_token,
                histories=range_data.histories,
                trade_dates=range_data.trade_dates,
            )
            candidate = _candidate_or_none(params=params, result=result, score_key=score_key, period=period)
            if candidate is not None:
                candidates.append(candidate)
            if progress_callback is not None:
                pct = progress_start + (progress_end - progress_start) * ((index + 1) / total)
                progress_callback(pct, f"{period.upper()} 参数组合 {index + 1}/{len(param_sets)}")
        ranked = sorted(candidates, key=lambda item: item.score, reverse=True)
        return [replace(item, rank=index + 1) for index, item in enumerate(ranked)]

    def run_params(
        self,
        base_config: BacktestConfig,
        *,
        params: dict[str, Any],
        start_date: str,
        end_date: str,
        cancel_token: Any | None = None,
        histories: dict[str, list[DailyBar]] | None = None,
        trade_dates: list[str] | None = None,
    ) -> BacktestResult:
        config = _config_for_params(
            self.engine,
            replace(base_config, start_date=start_date, end_date=end_date),
            params,
            histories=histories,
        )
        return _run_engine(
            self.engine,
            config,
            cancel_token=cancel_token,
            histories_override=histories,
            trade_dates_override=trade_dates,
        )


def enumerate_param_sets(
    param_grid: dict[str, list[Any]],
    *,
    max_combinations: int = 500,
    seed: int = 20260505,
) -> tuple[list[dict[str, Any]], int, bool]:
    invalid = sorted(set(param_grid) - ALLOWED_OPTIMIZATION_PARAMS)
    if invalid:
        raise ValueError(f"不支持优化参数: {', '.join(invalid)}")
    keys = list(param_grid)
    values = [list(param_grid[key]) for key in keys]
    total_count = 1
    for item in values:
        total_count *= max(len(item), 1)
    combinations = [dict(zip(keys, combination)) for combination in product(*values)]
    if len(combinations) <= max_combinations:
        return combinations, total_count, False
    sampler = random.Random(seed)
    return sampler.sample(combinations, max_combinations), total_count, True


def _validate_oos_ranges(train_start: str, train_end: str, test_start: str, test_end: str) -> None:
    if not all([train_start, train_end, test_start, test_end]):
        raise ValueError("参数优化必须提供样本内训练期和样本外测试期。")
    if train_start > train_end or test_start > test_end:
        raise ValueError("参数优化训练期或样本外测试期日期范围无效。")
    if train_end >= test_start:
        raise ValueError("参数优化必须先训练、后样本外验证，禁止全量历史直接寻优。")


def _prepare_range_data(engine: BacktestEngine, base_config: BacktestConfig, start_date: str, end_date: str) -> _RangeData:
    config = replace(base_config, start_date=start_date, end_date=end_date)
    signals = list(config.signals) or engine.data_provider.load_low_buy_signals(
        strategies=config.strategies,
        start_date=start_date,
        end_date=end_date,
        max_signals_per_day=config.max_signals_per_day,
    )
    benchmark_symbol = str(config.benchmark_symbol or "").strip()
    symbols = sorted({signal.symbol for signal in signals} | ({benchmark_symbol} if benchmark_symbol else set()))
    trade_dates = _fetch_trade_dates(engine, start_date, end_date)
    histories = _fetch_bars(engine, symbols, start_date, end_date)
    return _RangeData(config=replace(config, signals=signals), trade_dates=trade_dates, histories=histories)


def _fetch_trade_dates(engine: BacktestEngine, start_date: str, end_date: str) -> list[str]:
    try:
        return list(engine.data_provider.fetch_trade_dates(start_date, end_date))
    except Exception as exc:
        raise RuntimeError(f"回测优化无法读取交易日历: {start_date} 至 {end_date}") from exc


def _fetch_bars(
    engine: BacktestEngine,
    symbols: list[str],
    start_date: str,
    end_date: str,
) -> dict[str, list[DailyBar]]:
    if not symbols:
        return {}
    try:
        return engine.data_provider.fetch_bars(symbols, start_date=start_date, end_date=end_date)
    except Exception as exc:
        raise RuntimeError(f"回测优化无法读取日线行情: {start_date} 至 {end_date}") from exc


def _config_for_params(
    engine: BacktestEngine,
    base_config: BacktestConfig,
    params: dict[str, Any],
    *,
    histories: dict[str, list[DailyBar]] | None = None,
) -> BacktestConfig:
    max_position_pct = _optional_float(params.get("max_position_pct"))
    config = base_config
    if max_position_pct is not None:
        config = replace(config, max_position_pct=max_position_pct)
    signals = list(config.signals)
    if not signals:
        signals = engine.data_provider.load_low_buy_signals(
            strategies=config.strategies,
            start_date=config.start_date,
            end_date=config.end_date,
            max_signals_per_day=config.max_signals_per_day,
        )
    if params:
        signal_histories = histories
        if signal_histories is None:
            signal_histories = engine.data_provider.fetch_bars(
                [signal.symbol for signal in signals],
                start_date=config.start_date,
                end_date=config.end_date,
            )
        signals = _apply_signal_params(signals, signal_histories, config.execution_model, params)
    return replace(config, signals=signals)


def _run_engine(
    engine: BacktestEngine,
    config: BacktestConfig,
    *,
    cancel_token: Any | None,
    histories_override: dict[str, list[DailyBar]] | None,
    trade_dates_override: list[str] | None,
) -> BacktestResult:
    try:
        return engine.run(
            config,
            cancel_token=cancel_token,
            histories_override=histories_override,
            trade_dates_override=trade_dates_override,
        )
    except TypeError as exc:
        message = str(exc)
        if "histories_override" not in message and "trade_dates_override" not in message:
            raise
        return engine.run(config, cancel_token=cancel_token)


def _apply_signal_params(
    signals: list[BacktestSignal],
    histories: dict[str, list[DailyBar]],
    execution_model: str,
    params: dict[str, Any],
) -> list[BacktestSignal]:
    min_score = _optional_float(params.get("min_score"))
    max_holding_days = _optional_int(params.get("max_holding_days"))
    stop_loss_pct = _optional_float(params.get("stop_loss_pct"))
    take_profit_pct = _optional_float(params.get("take_profit_pct"))
    position_pct = _optional_float(params.get("max_position_pct"))
    bars_by_symbol_date = {
        (symbol, bar.trade_date): bar for symbol, bars in histories.items() for bar in bars
    }
    output: list[BacktestSignal] = []
    for signal in signals:
        if min_score is not None and signal.score < min_score:
            continue
        bar = bars_by_symbol_date.get((signal.symbol, signal.signal_date))
        entry_price = _estimated_entry_price(bar, signal, execution_model)
        output.append(
            replace(
                signal,
                max_holding_days=max_holding_days or signal.max_holding_days,
                stop_loss=_price_from_pct(entry_price, stop_loss_pct, signal.stop_loss),
                take_profit=_price_from_pct(entry_price, take_profit_pct, signal.take_profit),
                position_pct=position_pct if position_pct is not None else signal.position_pct,
            )
        )
    return output


def _candidate(*, params: dict[str, Any], result: BacktestResult, score_key: str, period: str, rank: int = 0) -> OptimizationCandidate:
    metric_key = TARGET_METRIC_KEYS.get(score_key, score_key)
    metrics = _candidate_metrics(result.metrics, result.trades)
    return OptimizationCandidate(
        params=dict(params),
        score=_float(metrics.get(metric_key), 0.0),
        metrics=metrics,
        period=period,
        rank=rank,
    )


def _candidate_or_none(
    *,
    params: dict[str, Any],
    result: BacktestResult,
    score_key: str,
    period: str,
    rank: int = 0,
) -> OptimizationCandidate | None:
    if result.status != "succeeded":
        return None
    return _candidate(params=params, result=result, score_key=score_key, period=period, rank=rank)


def _candidate_metrics(metrics: dict[str, Any], trades: list[Any]) -> dict[str, Any]:
    trade_count = int(metrics.get("trade_count") or len(trades) or 0)
    stop_loss_count = sum(1 for trade in trades if getattr(trade, "exit_reason", "") == "stop_loss")
    attribution = metrics.get("attribution") if isinstance(metrics.get("attribution"), dict) else {}
    output = {
        "total_return_pct": _float(metrics.get("total_return_pct"), 0.0),
        "win_rate_pct": _float(metrics.get("win_rate_pct"), 0.0),
        "stop_loss_rate_pct": round(stop_loss_count / max(trade_count, 1) * 100, 4),
        "max_drawdown_pct": _float(metrics.get("max_drawdown_pct"), 0.0),
        "profit_factor": _float(metrics.get("profit_factor"), 0.0),
        "sharpe_ratio": _float(metrics.get("sharpe_ratio"), 0.0),
        "trade_count": trade_count,
        "market_state_attribution": list(attribution.get("market_state") or []),
    }
    return output


def _is_oos_downgrade(is_metrics: dict[str, Any], oos_metrics: dict[str, Any]) -> bool:
    is_sharpe = _float(is_metrics.get("sharpe_ratio"), 0.0)
    oos_sharpe = _float(oos_metrics.get("sharpe_ratio"), 0.0)
    is_return = _float(is_metrics.get("total_return_pct"), 0.0)
    oos_return = _float(oos_metrics.get("total_return_pct"), 0.0)
    return oos_sharpe < 0 or (is_return > 0 and oos_return < is_return * 0.5)


def _estimated_entry_price(bar: DailyBar | None, signal: BacktestSignal, execution_model: str) -> float | None:
    if bar is None:
        return signal.entry_zone_high or signal.entry_zone_low
    if execution_model in {"open_price", "next_open"}:
        return bar.open_price
    if execution_model == "vwap":
        return bar.vwap
    if execution_model == "close_price":
        return bar.close_price
    if execution_model == "entry_zone_touch" and signal.entry_zone_high:
        return signal.entry_zone_high
    return max(bar.open_price, bar.close_price)


def _price_from_pct(entry_price: float | None, pct: float | None, fallback: float | None) -> float | None:
    if entry_price is None or entry_price <= 0 or pct is None:
        return fallback
    return round(entry_price * (1 + pct), 4)


def _cancel_requested(cancel_token: Any | None) -> bool:
    if cancel_token is None:
        return False
    checker = getattr(cancel_token, "is_cancelled", None)
    if callable(checker):
        return bool(checker())
    return bool(getattr(cancel_token, "cancelled", False))


def _optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return _float(value, 0.0)


def _optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
