from __future__ import annotations

from typing import Any

import pandas as pd

from app.models.schemas import LowBuyCandidateOut
from app.services.low_buy.execution_simulation import (
    DailyExecutionBar,
    ExecutionSimulationOverride,
    bars_from_history_frame,
    simulate_candidate_execution,
    simulate_candidate_execution_from_future_rows,
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
    execution_override: ExecutionSimulationOverride | None = None,
) -> TradeOutcome | None:
    signal_index = _bar_index(bars, signal_date)
    if signal_index is None:
        return None
    future = bars[signal_index + 1 :]
    forward = future[:forward_days]
    if len(forward) < forward_days:
        return None
    return _evaluate_candidate_outcome_from_future_rows(
        candidate=candidate,
        signal_date=signal_date,
        future=future,
        forward=forward,
        forward_days=forward_days,
        execution_override=execution_override,
    )


def _evaluate_candidate_outcome_from_future_rows(
    *,
    candidate: LowBuyCandidateOut,
    signal_date: str,
    future: list[DailyExecutionBar],
    forward: list[DailyExecutionBar],
    forward_days: int,
    execution_override: ExecutionSimulationOverride | None = None,
) -> TradeOutcome | None:
    entry = max(candidate.entry_zone_low, min(candidate.latest_price, candidate.entry_zone_high))
    if entry <= 0:
        return None
    execution = simulate_candidate_execution_from_future_rows(
        candidate=candidate,
        signal_trade_date=signal_date,
        future_rows=future,
        override=execution_override,
    )
    event_metrics = _next_day_event_metrics_from_bars(forward=forward, entry=entry)
    return _trade_outcome_from_execution(
        candidate=candidate,
        signal_date=signal_date,
        entry=entry,
        forward=forward,
        forward_days=forward_days,
        execution=execution,
        event_metrics=event_metrics,
    )


def evaluate_candidate_outcomes_from_bars(
    *,
    candidate: LowBuyCandidateOut,
    signal_date: str,
    bars: list[DailyExecutionBar],
    forward_days: int,
    execution_overrides: dict[str, ExecutionSimulationOverride | None],
) -> dict[str, TradeOutcome] | None:
    signal_index = _bar_index(bars, signal_date)
    if signal_index is None:
        return None
    future = bars[signal_index + 1 :]
    forward = future[:forward_days]
    if len(forward) < forward_days:
        return None
    entry = max(candidate.entry_zone_low, min(candidate.latest_price, candidate.entry_zone_high))
    if entry <= 0:
        return None
    event_metrics = _next_day_event_metrics_from_bars(forward=forward, entry=entry)
    return {
        key: _trade_outcome_from_execution(
            candidate=candidate,
            signal_date=signal_date,
            entry=entry,
            forward=forward,
            forward_days=forward_days,
            execution=simulate_candidate_execution_from_future_rows(
                candidate=candidate,
                signal_trade_date=signal_date,
                future_rows=future,
                override=override,
            ),
            event_metrics=event_metrics,
        )
        for key, override in execution_overrides.items()
    }


def _trade_outcome_from_execution(
    *,
    candidate: LowBuyCandidateOut,
    signal_date: str,
    entry: float,
    forward: list[DailyExecutionBar],
    forward_days: int,
    execution,
    event_metrics: dict[str, Any],
) -> TradeOutcome:
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
        entry_zone_low=_safe_float(getattr(candidate, "entry_zone_low", 0.0)),
        entry_zone_high=_safe_float(getattr(candidate, "entry_zone_high", 0.0)),
        spike_return_1d=_spike_return(forward, entry, 1),
        spike_return_2d=_spike_return(forward, entry, 2),
        spike_return_3d=_spike_return(forward, entry, 3),
        spike_return_4d=_spike_return(forward, entry, 4),
        spike_return_5d=_spike_return(forward, entry, 5),
        entry_trade_date=execution.entry_trade_date or "",
        exit_trade_date=execution.exit_trade_date or "",
        **_candidate_production_scoring_fields(candidate, signal_date=signal_date, forward=forward),
        **_candidate_market_state_fields(candidate),
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
    execution_override: ExecutionSimulationOverride | None = None,
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
        override=execution_override,
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
        entry_zone_low=_safe_float(getattr(candidate, "entry_zone_low", 0.0)),
        entry_zone_high=_safe_float(getattr(candidate, "entry_zone_high", 0.0)),
        spike_return_1d=_spike_return_from_frame(forward, entry, 1),
        spike_return_2d=_spike_return_from_frame(forward, entry, 2),
        spike_return_3d=_spike_return_from_frame(forward, entry, 3),
        spike_return_4d=_spike_return_from_frame(forward, entry, 4),
        spike_return_5d=_spike_return_from_frame(forward, entry, 5),
        entry_trade_date=execution.entry_trade_date or "",
        exit_trade_date=execution.exit_trade_date or "",
        **_candidate_production_scoring_fields(candidate, signal_date=signal_date, forward=forward),
        **_candidate_market_state_fields(candidate),
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


def _spike_return(rows: list, entry: float, holding_days: int) -> float:
    end = min(max(holding_days, 1), len(rows))
    high = max(float(row.high_price) for row in rows[:end])
    return round((high / entry - 1) * 100, 4)


def _spike_return_from_frame(frame: pd.DataFrame, entry: float, holding_days: int) -> float:
    end = min(max(holding_days, 1), len(frame))
    high = float(frame.iloc[:end]["high"].max())
    return round((high / entry - 1) * 100, 4)


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
        t1_open=float(t1.open_price),
        t1_pct_chg=float(getattr(t1, "pct_chg", 0.0) or 0.0),
        t1_high_price=float(t1.high_price),
        t1_low_price=float(t1.low_price),
        t1_high=t1_high,
        t1_close=t1_close,
        t2_high=t2_high,
        t2_close=t2_close,
        entry=entry,
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
        t1_open=float(t1["open"]),
        t1_pct_chg=float(t1.get("pct_chg", 0.0) or 0.0),
        t1_high_price=float(t1["high"]),
        t1_low_price=float(t1["low"]),
        t1_high=t1_high,
        t1_close=t1_close,
        t2_high=t2_high,
        t2_close=t2_close,
        entry=entry,
    )


def _next_day_event_metrics(
    *,
    t1_open: float,
    t1_pct_chg: float,
    t1_high_price: float,
    t1_low_price: float,
    t1_high: float,
    t1_close: float,
    t2_high: float,
    t2_close: float,
    entry: float,
) -> dict[str, Any]:
    return {
        "t1_open_return_pct": round((float(t1_open) / max(float(entry), 0.01) - 1) * 100.0, 4),
        "t1_pct_chg": round(float(t1_pct_chg), 4),
        "t1_locked_limit_up": bool(float(t1_pct_chg) >= 9.7 and abs(float(t1_high_price) - float(t1_low_price)) <= 0.001),
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
    return _next_day_event_metrics(
        t1_open=0.0,
        t1_pct_chg=0.0,
        t1_high_price=0.0,
        t1_low_price=0.0,
        t1_high=0.0,
        t1_close=0.0,
        t2_high=0.0,
        t2_close=0.0,
        entry=1.0,
    )


def _candidate_market_state_fields(candidate: LowBuyCandidateOut) -> dict[str, Any]:
    return {
        "market_state": str(getattr(candidate, "market_state", "") or ""),
        "market_state_text": str(getattr(candidate, "market_state_text", "") or ""),
        "market_state_category": str(getattr(candidate, "market_state_category", "") or ""),
        "market_state_strength": _safe_float(getattr(candidate, "market_state_strength", 0.0)),
    }


def _candidate_production_scoring_fields(
    candidate: LowBuyCandidateOut,
    *,
    signal_date: str,
    forward: list,
) -> dict[str, Any]:
    return_start_time = _forward_start_date(forward)
    return {
        "sector_name": str(getattr(candidate, "sector_name", "") or ""),
        "production_score": getattr(candidate, "production_score", None),
        "watch_score": getattr(candidate, "watch_score", None),
        "production_decision": str(getattr(candidate, "production_decision", "") or ""),
        "front_row_tier": str(getattr(candidate, "front_row_tier", "unknown") or "unknown"),
        "score_cap": getattr(candidate, "score_cap", None),
        "score_components": dict(getattr(candidate, "score_components", {}) or {}),
        "exclusion_reasons": list(getattr(candidate, "exclusion_reasons", []) or []),
        "warning_tags": list(getattr(candidate, "warning_tags", []) or []),
        "production_scoring_config_version": str(getattr(candidate, "production_scoring_config_version", "") or ""),
        "signal_generated_at": signal_date,
        "data_cutoff_time": signal_date,
        "return_start_time": return_start_time,
    }


def _forward_start_date(forward: Any) -> str:
    if forward is None:
        return ""
    if isinstance(forward, pd.DataFrame):
        if forward.empty:
            return ""
        return str(forward.iloc[0].get("date", "") or "")
    try:
        if len(forward) <= 0:
            return ""
        return str(getattr(forward[0], "trade_date", "") or "")
    except (TypeError, KeyError, IndexError):
        return ""


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
