from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Iterable

from app.models.schemas import LowBuyCandidateOut, LowBuyExecutionBacktestItemOut

ROUND_TRIP_COST_BPS = 16.0


@dataclass(frozen=True)
class DailyExecutionBar:
    trade_date: str
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    pct_chg: float


@dataclass(frozen=True)
class ExecutionSimulationOverride:
    """Research-only execution overrides used by offline backtests.

    Production paths keep passing no override, so candidate strategy semantics
    and live/simulated trading rules remain unchanged.
    """

    stop_loss_pct: float | None = None
    atr_stop_multiplier: float | None = None
    first_take_profit_pct: float | None = None
    trailing_stop_pct: float | None = None
    max_holding_days: int | None = None
    force_t1_exit: bool = False
    force_t2_exit: bool = False
    enforce_t1_exit_rules: bool = False


def bars_from_repository_rows(rows: Iterable[object]) -> list[DailyExecutionBar]:
    return [
        DailyExecutionBar(
            trade_date=str(row.trade_date),
            open_price=float(row.open_price),
            high_price=float(row.high_price),
            low_price=float(row.low_price),
            close_price=float(row.close_price),
            pct_chg=float(row.pct_chg),
        )
        for row in rows
    ]


def bars_from_history_frame(history) -> list[DailyExecutionBar]:
    return [
        DailyExecutionBar(
            trade_date=str(row["date"]),
            open_price=float(row["open"]),
            high_price=float(row["high"]),
            low_price=float(row["low"]),
            close_price=float(row["close"]),
            pct_chg=float(row["pct_chg"]),
        )
        for _, row in history.iterrows()
    ]


def simulate_candidate_execution(
    *,
    candidate: LowBuyCandidateOut,
    rows: list[DailyExecutionBar],
    override: ExecutionSimulationOverride | None = None,
) -> LowBuyExecutionBacktestItemOut:
    signal_trade_date = candidate.confirmed_trade_date or candidate.quote_timestamp
    future_rows = [row for row in rows if row.trade_date > signal_trade_date]
    return simulate_candidate_execution_from_future_rows(
        candidate=candidate,
        signal_trade_date=signal_trade_date,
        future_rows=future_rows,
        override=override,
    )


def simulate_candidate_execution_from_future_rows(
    *,
    candidate: LowBuyCandidateOut,
    signal_trade_date: str,
    future_rows: list[DailyExecutionBar],
    override: ExecutionSimulationOverride | None = None,
) -> LowBuyExecutionBacktestItemOut:
    if not future_rows:
        return _not_filled(candidate, signal_trade_date, "缺少信号后的日线数据。")

    entry = _find_entry(candidate, future_rows[:2])
    if entry is None:
        return _not_filled(candidate, signal_trade_date, "信号后 2 日未出现可成交买点。")

    entry_row, entry_price = entry
    holding_rows = [
        row
        for row in future_rows
        if row.trade_date >= entry_row.trade_date
    ][: max(candidate.exit_plan.max_holding_days, 1)]
    return _simulate_exit(candidate, signal_trade_date, entry_row.trade_date, entry_price, holding_rows, override=override)


def _find_entry(candidate: LowBuyCandidateOut, rows: list[DailyExecutionBar]) -> tuple[DailyExecutionBar, float] | None:
    for row in rows:
        if _is_locked_limit_up(row):
            continue
        if row.open_price < candidate.stop_loss:
            return None
        if row.low_price <= candidate.entry_zone_high and row.high_price >= candidate.entry_zone_low:
            if candidate.entry_zone_low <= row.open_price <= candidate.entry_zone_high:
                return row, row.open_price
            if row.open_price > candidate.entry_zone_high:
                return row, candidate.entry_zone_high
            return row, max(row.open_price, candidate.entry_zone_low)
        if _is_right_side_strategy(candidate.strategy_key) and row.open_price <= candidate.entry_zone_high * 1.018:
            return row, row.open_price
    return None


def _simulate_exit(
    candidate: LowBuyCandidateOut,
    signal_trade_date: str,
    entry_trade_date: str,
    entry_price: float,
    rows: list[DailyExecutionBar],
    *,
    override: ExecutionSimulationOverride | None = None,
) -> LowBuyExecutionBacktestItemOut:
    stop_loss, first_take_profit, trailing_stop, max_holding_days = _resolve_exit_levels(
        candidate=candidate,
        entry_price=entry_price,
        override=override,
    )
    rows = rows[:max(max_holding_days, 1)]
    max_gain = 0.0
    max_drawdown = 0.0
    exit_price = rows[-1].close_price
    exit_trade_date = rows[-1].trade_date
    exit_reason = "到达最长持有天数，按收盘价退出。"

    for row in rows:
        max_gain = max(max_gain, _return_pct(row.high_price, entry_price))
        max_drawdown = min(max_drawdown, _return_pct(row.low_price, entry_price))
        same_day_entry = row.trade_date == entry_trade_date
        if row.open_price <= stop_loss:
            exit_price = row.open_price
            exit_trade_date = row.trade_date
            exit_reason = "开盘跳空跌破止损位，按开盘价退出。"
            break
        if _exit_allowed_on_bar(override, same_day_entry=same_day_entry) and row.low_price <= stop_loss:
            exit_price = stop_loss
            exit_trade_date = row.trade_date
            exit_reason = "触发止损位。"
            break
        if _exit_allowed_on_bar(override, same_day_entry=same_day_entry) and row.high_price >= first_take_profit:
            exit_price = first_take_profit
            exit_trade_date = row.trade_date
            exit_reason = "触发首次止盈位。"
            break
        if row.low_price <= trailing_stop and not same_day_entry:
            exit_price = trailing_stop
            exit_trade_date = row.trade_date
            exit_reason = "触发移动防守线。"
            break
        if override and override.force_t1_exit and row.trade_date != entry_trade_date:
            exit_price = row.close_price
            exit_trade_date = row.trade_date
            exit_reason = "研究模型 T+1 收盘退出。"
            break
        if override and override.force_t2_exit and row.trade_date != entry_trade_date:
            elapsed_rows = [item for item in rows if item.trade_date >= entry_trade_date and item.trade_date <= row.trade_date]
            if len(elapsed_rows) >= 3:
                exit_price = row.close_price
                exit_trade_date = row.trade_date
                exit_reason = "研究模型 T+2 收盘退出。"
                break

    net_return = _return_pct(exit_price, entry_price) - ROUND_TRIP_COST_BPS / 100
    return LowBuyExecutionBacktestItemOut(
        symbol=candidate.symbol,
        name=candidate.name,
        strategy_key=candidate.strategy_key,
        signal_trade_date=signal_trade_date,
        entry_trade_date=entry_trade_date,
        exit_trade_date=exit_trade_date,
        status="filled",
        entry_price=round(entry_price, 3),
        exit_price=round(exit_price, 3),
        net_return_pct=round(net_return, 3),
        max_gain_pct=round(max_gain, 3),
        max_drawdown_pct=round(max_drawdown, 3),
        exit_reason=exit_reason,
    )


def _not_filled(candidate: LowBuyCandidateOut, signal_trade_date: str, reason: str) -> LowBuyExecutionBacktestItemOut:
    return LowBuyExecutionBacktestItemOut(
        symbol=candidate.symbol,
        name=candidate.name,
        strategy_key=candidate.strategy_key,
        signal_trade_date=signal_trade_date,
        status="not_filled",
        exit_reason=reason,
    )


def _resolve_exit_levels(
    *,
    candidate: LowBuyCandidateOut,
    entry_price: float,
    override: ExecutionSimulationOverride | None,
) -> tuple[float, float, float, int]:
    stop_loss = candidate.exit_plan.stop_loss or candidate.stop_loss
    first_take_profit = candidate.exit_plan.first_take_profit or candidate.take_profit
    trailing_stop = max(candidate.exit_plan.trailing_stop, stop_loss)
    max_holding_days = int(candidate.exit_plan.max_holding_days or 1)
    if override is None:
        return stop_loss, first_take_profit, trailing_stop, max_holding_days

    if override.stop_loss_pct is not None:
        stop_loss = round(entry_price * (1.0 + float(override.stop_loss_pct) / 100.0), 3)
    if override.atr_stop_multiplier is not None and candidate.atr_pct > 0:
        atr_stop_pct = -abs(float(candidate.atr_pct) * float(override.atr_stop_multiplier))
        stop_loss = round(entry_price * (1.0 + atr_stop_pct / 100.0), 3)
    if override.first_take_profit_pct is not None:
        first_take_profit = round(entry_price * (1.0 + float(override.first_take_profit_pct) / 100.0), 3)
    if override.trailing_stop_pct is not None:
        trailing_stop = round(entry_price * (1.0 + float(override.trailing_stop_pct) / 100.0), 3)
    if override.max_holding_days is not None:
        max_holding_days = max(int(override.max_holding_days), 1)
    if override.force_t1_exit:
        max_holding_days = max(max_holding_days, 2)
    if override.force_t2_exit:
        max_holding_days = max(max_holding_days, 3)
    return stop_loss, first_take_profit, max(trailing_stop, stop_loss), max_holding_days


def _exit_allowed_on_bar(override: ExecutionSimulationOverride | None, *, same_day_entry: bool) -> bool:
    if not same_day_entry:
        return True
    if override and override.enforce_t1_exit_rules:
        return False
    return True


def _is_locked_limit_up(row: DailyExecutionBar) -> bool:
    return row.pct_chg >= 9.7 and abs(row.high_price - row.low_price) <= 0.001


def _is_right_side_strategy(strategy_key: str) -> bool:
    return strategy_key in {"divergence_consensus", "limit_up_breakout_retrace"}


def _return_pct(price: float, entry_price: float) -> float:
    return (price - entry_price) / max(entry_price, 0.01) * 100


def simulate_liquidity_crisis(
    filled_signals: list[dict],
    *,
    crisis_ratio: float = 0.05,
    crisis_extra_loss_pct: float = -25.0,
) -> dict:
    """Stress test a small share of filled trades with additional illiquidity loss."""

    if not filled_signals:
        return {
            "scenario": "liquidity_crisis",
            "crisis_count": 0,
            "crisis_ratio_pct": round(crisis_ratio * 100, 1),
            "crisis_extra_loss_pct": crisis_extra_loss_pct,
            "original_avg_return": 0.0,
            "crisis_avg_return": 0.0,
            "impact_pct": 0.0,
        }

    rng = random.Random(42)
    n_crisis = max(1, int(len(filled_signals) * crisis_ratio))
    crisis_indices = set(rng.sample(range(len(filled_signals)), min(n_crisis, len(filled_signals))))
    original_returns = [float(item.get("net_return_pct", 0.0) or 0.0) for item in filled_signals]
    adjusted_returns = [
        value + crisis_extra_loss_pct if index in crisis_indices else value
        for index, value in enumerate(original_returns)
    ]
    original_avg = sum(original_returns) / len(original_returns)
    crisis_avg = sum(adjusted_returns) / len(adjusted_returns)
    return {
        "scenario": "liquidity_crisis",
        "crisis_count": len(crisis_indices),
        "crisis_ratio_pct": round(crisis_ratio * 100, 1),
        "crisis_extra_loss_pct": crisis_extra_loss_pct,
        "original_avg_return": round(original_avg, 3),
        "crisis_avg_return": round(crisis_avg, 3),
        "impact_pct": round(crisis_avg - original_avg, 3),
    }
