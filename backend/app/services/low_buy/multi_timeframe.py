from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class MultiTimeframeResonance:
    score: float = 0.0
    text: str = "多周期共振不足"
    weekly_ma10_support: bool = False
    monthly_ma20_intact: bool = False


def evaluate_multi_timeframe_resonance(history: pd.DataFrame, latest_close: float) -> MultiTimeframeResonance:
    if history is None or history.empty or latest_close <= 0:
        return MultiTimeframeResonance()
    weekly = _aggregate_ohlcv(history, "W-FRI")
    monthly = _aggregate_ohlcv(history, "M")
    weekly_support = _weekly_ma10_support(weekly, latest_close)
    monthly_intact = _monthly_ma20_intact(monthly, latest_close)
    score = 0.0
    reasons: list[str] = []
    if weekly_support:
        score += 2.5
        reasons.append("周线 MA10 附近有支撑")
    if monthly_intact:
        score += 2.5
        reasons.append("月线未破 MA20")
    return MultiTimeframeResonance(
        score=round(min(score, 5.0), 2),
        text="；".join(reasons) if reasons else "周线/月线支撑共振不足",
        weekly_ma10_support=weekly_support,
        monthly_ma20_intact=monthly_intact,
    )


def _aggregate_ohlcv(history: pd.DataFrame, rule: str) -> pd.DataFrame:
    frame = history.copy()
    if "amount" not in frame.columns:
        frame["amount"] = 0.0
    if "volume" not in frame.columns:
        frame["volume"] = 0.0
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame.set_index("date").sort_index()
    aggregated = frame.resample(rule).agg(
        {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
            "amount": "sum",
        }
    )
    return aggregated.dropna(subset=["open", "high", "low", "close"])


def _weekly_ma10_support(weekly: pd.DataFrame, latest_close: float) -> bool:
    if len(weekly) < 10:
        return False
    ma10 = float(weekly["close"].rolling(10).mean().iloc[-1])
    latest_low = _last_value(weekly, "low")
    latest_week_close = _last_value(weekly, "close")
    if ma10 <= 0:
        return False
    near_support = abs(latest_close - ma10) / ma10 * 100 <= 6.0
    support_held = min(latest_low, latest_close) >= ma10 * 0.965
    return near_support and support_held and latest_week_close >= ma10 * 0.985


def _monthly_ma20_intact(monthly: pd.DataFrame, latest_close: float) -> bool:
    if len(monthly) < 20:
        return False
    ma20 = float(monthly["close"].rolling(20).mean().iloc[-1])
    if ma20 <= 0:
        return False
    return latest_close >= ma20 * 0.98


def _last_value(frame: pd.DataFrame, column: str) -> float:
    value: Any = frame[column].iloc[-1] if column in frame else 0.0
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
