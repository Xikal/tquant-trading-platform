from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from app.models.schemas import KlineBar, QuoteSnapshot


@dataclass(frozen=True)
class CandleDistributionFeatures:
    body_pct: float
    upper_shadow_ratio: float
    lower_shadow_ratio: float
    close_position_ratio: float
    doji_like: bool
    long_lower_shadow: bool
    long_upper_shadow: bool
    weak_close: bool


@dataclass(frozen=True)
class DistributionSnapshot:
    upper_shadow_ratio: float
    close_position_ratio: float
    weak_close: bool
    long_upper_shadow: bool
    false_breakout_flag: bool
    stall_after_volume_flag: bool
    intraday_reversal_flag: bool
    distribution_risk_score: float


def build_candle_distribution_features(
    *,
    open_price: float,
    high_price: float,
    low_price: float,
    close_price: float,
) -> CandleDistributionFeatures:
    intraday_range = max(high_price - low_price, 0.01)
    body_pct = abs(close_price - open_price) / max(abs(open_price), 0.01) * 100
    upper_shadow = high_price - max(open_price, close_price)
    lower_shadow = min(open_price, close_price) - low_price
    close_position_ratio = (close_price - low_price) / intraday_range
    upper_shadow_ratio = max(upper_shadow, 0.0) / intraday_range
    lower_shadow_ratio = max(lower_shadow, 0.0) / intraday_range
    return CandleDistributionFeatures(
        body_pct=body_pct,
        upper_shadow_ratio=round(upper_shadow_ratio, 4),
        lower_shadow_ratio=round(lower_shadow_ratio, 4),
        close_position_ratio=round(close_position_ratio, 4),
        doji_like=body_pct <= 1.1,
        long_lower_shadow=lower_shadow_ratio >= 0.35,
        long_upper_shadow=upper_shadow_ratio >= 0.35,
        weak_close=close_position_ratio <= 0.38,
    )


def build_daily_distribution_snapshot(
    *,
    open_price: float,
    high_price: float,
    low_price: float,
    close_price: float,
    latest_change_pct: float,
    breakout_level: float,
    reference_high: float,
    volume_burst_ratio: float,
    latest_volume_ratio: float,
    post_volume_ratio: float,
) -> tuple[CandleDistributionFeatures, DistributionSnapshot]:
    candle = build_candle_distribution_features(
        open_price=open_price,
        high_price=high_price,
        low_price=low_price,
        close_price=close_price,
    )
    false_breakout_flag = (
        breakout_level > 0
        and high_price >= breakout_level * 1.008
        and close_price < breakout_level * 0.996
        and candle.weak_close
    )
    stall_after_volume_flag = (
        volume_burst_ratio >= 1.7
        and post_volume_ratio >= 0.68
        and latest_volume_ratio >= 0.36
        and abs(latest_change_pct) <= 2.2
        and close_price < reference_high * 0.995
    )
    intraday_reversal_flag = (
        candle.long_upper_shadow
        and candle.weak_close
        and latest_change_pct <= 1.8
    )
    distribution_risk_score = _distribution_risk_score(
        false_breakout_flag=false_breakout_flag,
        stall_after_volume_flag=stall_after_volume_flag,
        intraday_reversal_flag=intraday_reversal_flag,
        upper_shadow_ratio=candle.upper_shadow_ratio,
        weak_close=candle.weak_close,
    )
    snapshot = DistributionSnapshot(
        upper_shadow_ratio=candle.upper_shadow_ratio,
        close_position_ratio=candle.close_position_ratio,
        weak_close=candle.weak_close,
        long_upper_shadow=candle.long_upper_shadow,
        false_breakout_flag=false_breakout_flag,
        stall_after_volume_flag=stall_after_volume_flag,
        intraday_reversal_flag=intraday_reversal_flag,
        distribution_risk_score=distribution_risk_score,
    )
    return candle, snapshot


def build_intraday_distribution_snapshot(
    *,
    bars: Sequence[KlineBar],
    quote: QuoteSnapshot,
    vwap_value: float,
) -> DistributionSnapshot:
    if not bars:
        return _empty_distribution_snapshot()
    latest = bars[-1]
    candle = build_candle_distribution_features(
        open_price=latest.open,
        high_price=latest.high,
        low_price=latest.low,
        close_price=latest.close,
    )
    recent_high = max(float(bar.high) for bar in bars[-12:]) if bars else float(latest.high)
    previous_high = max((float(bar.high) for bar in bars[:-1]), default=recent_high)
    recent_closes = [float(bar.close) for bar in bars[-4:]]
    recent_volumes = [float(bar.volume) for bar in bars[-3:]]
    previous_volumes = [float(bar.volume) for bar in bars[-9:-3]]
    recent_volume_avg = sum(recent_volumes) / max(len(recent_volumes), 1)
    previous_volume_avg = sum(previous_volumes) / max(len(previous_volumes), 1) if previous_volumes else 0.0
    volume_expansion = (
        recent_volume_avg >= previous_volume_avg * 1.15
        if previous_volumes
        else False
    )
    close_band = (
        (max(recent_closes) - min(recent_closes)) / max(abs(quote.last_price), 0.01)
        if recent_closes
        else 0.0
    )
    false_breakout_flag = (
        recent_high >= max(previous_high, vwap_value) * 1.006
        and quote.last_price < recent_high * 0.994
        and quote.last_price < vwap_value * 0.999
        and candle.weak_close
    )
    stall_after_volume_flag = (
        volume_expansion
        and close_band <= 0.004
        and recent_high >= quote.last_price * 1.003
        and quote.last_price <= max(recent_closes) * 0.998
    )
    intraday_reversal_flag = (
        candle.long_upper_shadow
        and candle.weak_close
        and quote.last_price < vwap_value * 0.999
    )
    return DistributionSnapshot(
        upper_shadow_ratio=candle.upper_shadow_ratio,
        close_position_ratio=candle.close_position_ratio,
        weak_close=candle.weak_close,
        long_upper_shadow=candle.long_upper_shadow,
        false_breakout_flag=false_breakout_flag,
        stall_after_volume_flag=stall_after_volume_flag,
        intraday_reversal_flag=intraday_reversal_flag,
        distribution_risk_score=_distribution_risk_score(
            false_breakout_flag=false_breakout_flag,
            stall_after_volume_flag=stall_after_volume_flag,
            intraday_reversal_flag=intraday_reversal_flag,
            upper_shadow_ratio=candle.upper_shadow_ratio,
            weak_close=candle.weak_close,
        ),
    )


def _distribution_risk_score(
    *,
    false_breakout_flag: bool,
    stall_after_volume_flag: bool,
    intraday_reversal_flag: bool,
    upper_shadow_ratio: float,
    weak_close: bool,
) -> float:
    score = 0.0
    if false_breakout_flag:
        score += 5.0
    if stall_after_volume_flag:
        score += 3.0
    if intraday_reversal_flag:
        score += 2.5
    score += min(upper_shadow_ratio * 3.2, 1.8)
    if weak_close:
        score += 0.8
    return round(min(score, 10.0), 2)


def _empty_distribution_snapshot() -> DistributionSnapshot:
    return DistributionSnapshot(
        upper_shadow_ratio=0.0,
        close_position_ratio=0.0,
        weak_close=False,
        long_upper_shadow=False,
        false_breakout_flag=False,
        stall_after_volume_flag=False,
        intraday_reversal_flag=False,
        distribution_risk_score=0.0,
    )
