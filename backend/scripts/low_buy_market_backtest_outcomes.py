from __future__ import annotations

from typing import Any

import pandas as pd

from app.models.schemas import LowBuyCandidateOut
from app.services.low_buy.execution_simulation import (
    bars_from_history_frame,
    simulate_candidate_execution,
)

try:
    from .low_buy_market_backtest_reporting import TradeOutcome
except ImportError:
    from low_buy_market_backtest_reporting import TradeOutcome


def daily_rows_to_frame(rows, start_date_iso: str) -> pd.DataFrame | None:
    if not rows:
        return None
    frame = pd.DataFrame(
        [
            {
                "date": row.trade_date,
                "open": row.open_price,
                "close": row.close_price,
                "high": row.high_price,
                "low": row.low_price,
                "volume": row.volume,
                "amount": row.amount,
                "pct_chg": row.pct_chg,
            }
            for row in rows
        ]
    )
    frame = frame[frame["date"] >= start_date_iso].copy()
    if frame.empty:
        return None
    for column in ("open", "close", "high", "low", "volume", "amount", "pct_chg"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["open", "close", "high", "low", "volume", "pct_chg"])
    if frame.empty:
        return None
    frame["ma5"] = frame["close"].rolling(5).mean()
    frame["ma10"] = frame["close"].rolling(10).mean()
    frame["ma20"] = frame["close"].rolling(20).mean()
    frame["ma60"] = frame["close"].rolling(60).mean()
    return frame.reset_index(drop=True)


def history_frame_to_date(
    frame: pd.DataFrame | None,
    trade_date: str,
    *,
    history_window_days: int,
) -> pd.DataFrame | None:
    if frame is None or frame.empty:
        return None
    sliced = frame[frame["date"] <= trade_date]
    if sliced.empty:
        return None
    max_rows = max(80, min(history_window_days, 760))
    return sliced.tail(max_rows).reset_index(drop=True)


def evaluate_candidate_outcome_from_bars(
    *,
    candidate: LowBuyCandidateOut,
    signal_date: str,
    bars: list,
    forward_days: int,
) -> TradeOutcome | None:
    signal_index = _bar_index(bars, signal_date)
    if signal_index is None:
        return None
    forward = bars[signal_index + 1 : signal_index + 1 + forward_days]
    if len(forward) < forward_days:
        return None
    entry = max(candidate.entry_zone_low, min(candidate.latest_price, candidate.entry_zone_high))
    if entry <= 0:
        return None
    execution = simulate_candidate_execution(
        candidate=candidate.model_copy(update={"confirmed_trade_date": signal_date}),
        rows=bars,
    )
    event_metrics = _next_day_event_metrics_from_bars(forward=forward, entry=entry)
    return TradeOutcome(
        symbol=candidate.symbol,
        name=candidate.name,
        signal_date=signal_date,
        strategy_key=candidate.strategy_key,
        buy_signal_state=candidate.buy_signal_state,
        entry_price=round(entry, 4),
        execution_status=execution.status,
        net_return_pct=execution.net_return_pct,
        execution_exit_reason=execution.exit_reason,
        return_1d=_close_return(forward, entry, 1),
        return_2d=_close_return(forward, entry, 2),
        return_3d=_close_return(forward, entry, 3),
        return_4d=_close_return(forward, entry, 4),
        return_5d=_close_return(forward, entry, 5),
        max_gain_5d=round((max(row.high_price for row in forward) / entry - 1) * 100, 4),
        max_drawdown_5d=round((min(row.low_price for row in forward) / entry - 1) * 100, 4),
        **event_metrics,
    )


def evaluate_candidate_outcome(
    *,
    service,
    candidate: LowBuyCandidateOut,
    signal_date: str,
    latest_completed: str,
    forward_days: int,
    history_window_days: int,
) -> TradeOutcome | None:
    history = service._load_daily_history(
        symbol=candidate.symbol,
        latest_trade_date=latest_completed,
        history_window_days=history_window_days,
    )
    if history is None or history.empty:
        return None
    matches = history.index[history["date"] == signal_date].tolist()
    if not matches:
        return None
    signal_index = matches[-1]
    forward = history.iloc[signal_index + 1 : signal_index + 1 + forward_days]
    if len(forward) < forward_days:
        return None
    entry = max(candidate.entry_zone_low, min(candidate.latest_price, candidate.entry_zone_high))
    if entry <= 0:
        return None
    execution = simulate_candidate_execution(
        candidate=candidate.model_copy(update={"confirmed_trade_date": signal_date}),
        rows=bars_from_history_frame(history),
    )
    event_metrics = _next_day_event_metrics_from_frame(forward=forward, entry=entry)
    return TradeOutcome(
        symbol=candidate.symbol,
        name=candidate.name,
        signal_date=signal_date,
        strategy_key=candidate.strategy_key,
        buy_signal_state=candidate.buy_signal_state,
        entry_price=round(entry, 4),
        execution_status=execution.status,
        net_return_pct=execution.net_return_pct,
        execution_exit_reason=execution.exit_reason,
        return_1d=round((float(forward.iloc[0]["close"]) / entry - 1) * 100, 4),
        return_2d=round((float(forward.iloc[1]["close"]) / entry - 1) * 100, 4),
        return_3d=round((float(forward.iloc[min(2, len(forward) - 1)]["close"]) / entry - 1) * 100, 4),
        return_4d=round((float(forward.iloc[min(3, len(forward) - 1)]["close"]) / entry - 1) * 100, 4),
        return_5d=round((float(forward.iloc[forward_days - 1]["close"]) / entry - 1) * 100, 4),
        max_gain_5d=round((float(forward["high"].max()) / entry - 1) * 100, 4),
        max_drawdown_5d=round((float(forward["low"].min()) / entry - 1) * 100, 4),
        **event_metrics,
    )


def _bar_index(rows: list, trade_date: str) -> int | None:
    for index, row in enumerate(rows):
        if row.trade_date == trade_date:
            return index
    return None


def _close_return(rows: list, entry: float, holding_days: int) -> float:
    index = min(max(holding_days - 1, 0), len(rows) - 1)
    return round((rows[index].close_price / entry - 1) * 100, 4)


def _next_day_event_metrics_from_bars(*, forward: list, entry: float) -> dict[str, Any]:
    if len(forward) < 1:
        return _empty_next_day_event_metrics()
    t1 = forward[0]
    t2 = forward[1] if len(forward) >= 2 else forward[0]
    t1_high = round((float(t1.high_price) / entry - 1) * 100, 4)
    t1_close = round((float(t1.close_price) / entry - 1) * 100, 4)
    t2_high = round((float(t2.high_price) / entry - 1) * 100, 4)
    t2_close = round((float(t2.close_price) / entry - 1) * 100, 4)
    return _next_day_event_metrics(
        t1_high=t1_high,
        t1_close=t1_close,
        t2_high=t2_high,
        t2_close=t2_close,
    )


def _next_day_event_metrics_from_frame(*, forward: pd.DataFrame, entry: float) -> dict[str, Any]:
    if forward.empty:
        return _empty_next_day_event_metrics()
    t1 = forward.iloc[0]
    t2 = forward.iloc[1] if len(forward) >= 2 else forward.iloc[0]
    t1_high = (float(t1["high"]) / entry - 1) * 100
    t1_close = (float(t1["close"]) / entry - 1) * 100
    t2_high = (float(t2["high"]) / entry - 1) * 100
    t2_close = (float(t2["close"]) / entry - 1) * 100
    return _next_day_event_metrics(
        t1_high=t1_high,
        t1_close=t1_close,
        t2_high=t2_high,
        t2_close=t2_close,
    )


def _next_day_event_metrics(
    *,
    t1_high: float,
    t1_close: float,
    t2_high: float,
    t2_close: float,
) -> dict[str, Any]:
    return {
        "t1_high_return_pct": round(t1_high, 4),
        "t1_close_return_pct": round(t1_close, 4),
        "t1_spike_fade_pct": round(max(0.0, t1_high - t1_close), 4),
        "t2_high_return_pct": round(t2_high, 4),
        "t2_close_return_pct": round(t2_close, 4),
        "t1_hit_3_pct": t1_high >= 3.0,
        "t1_hit_5_pct": t1_high >= 5.0,
        "t1_fade_to_entry": t1_high >= 3.0 and t1_close <= 0.0,
    }


def _empty_next_day_event_metrics() -> dict[str, Any]:
    return _next_day_event_metrics(t1_high=0.0, t1_close=0.0, t2_high=0.0, t2_close=0.0)
