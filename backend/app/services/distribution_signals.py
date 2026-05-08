from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from app.models.schemas import KlineBar, QuoteSnapshot
from app.services.market.parameter_defaults import MARKET_DISTRIBUTION_SIGNAL_DEFAULTS


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
    params = _params()
    denominator_floor = _float_param(params, "denominator_floor")
    shadow_ratio_threshold = _float_param(params, "shadow_ratio_threshold")
    intraday_range = max(high_price - low_price, denominator_floor)
    body_pct = abs(close_price - open_price) / max(abs(open_price), denominator_floor) * 100
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
        doji_like=body_pct <= _float_param(params, "doji_body_pct_max"),
        long_lower_shadow=lower_shadow_ratio >= shadow_ratio_threshold,
        long_upper_shadow=upper_shadow_ratio >= shadow_ratio_threshold,
        weak_close=close_position_ratio <= _float_param(params, "weak_close_position_max"),
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
    params = _params()
    candle = build_candle_distribution_features(
        open_price=open_price,
        high_price=high_price,
        low_price=low_price,
        close_price=close_price,
    )
    false_breakout_flag = (
        breakout_level > 0
        and high_price >= breakout_level * _float_param(params, "false_breakout_high_multiplier")
        and close_price < breakout_level * _float_param(params, "false_breakout_close_multiplier")
        and candle.weak_close
    )
    stall_after_volume_flag = (
        volume_burst_ratio >= _float_param(params, "stall_volume_burst_min")
        and post_volume_ratio >= _float_param(params, "stall_post_volume_min")
        and latest_volume_ratio >= _float_param(params, "stall_latest_volume_min")
        and abs(latest_change_pct) <= _float_param(params, "stall_abs_change_max_pct")
        and close_price < reference_high * _float_param(params, "stall_reference_close_multiplier")
    )
    intraday_reversal_flag = (
        candle.long_upper_shadow
        and candle.weak_close
        and latest_change_pct <= _float_param(params, "reversal_latest_change_max_pct")
    )
    distribution_risk_score = _distribution_risk_score(
        false_breakout_flag=false_breakout_flag,
        stall_after_volume_flag=stall_after_volume_flag,
        intraday_reversal_flag=intraday_reversal_flag,
        upper_shadow_ratio=candle.upper_shadow_ratio,
        weak_close=candle.weak_close,
        params=params,
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
    params = _params()
    if not bars:
        return _empty_distribution_snapshot()
    latest = bars[-1]
    candle = build_candle_distribution_features(
        open_price=latest.open,
        high_price=latest.high,
        low_price=latest.low,
        close_price=latest.close,
    )
    recent_high_window = _int_param(params, "intraday_recent_high_window")
    close_window = _int_param(params, "intraday_close_window")
    recent_volume_window = _int_param(params, "intraday_recent_volume_window")
    previous_volume_window = _int_param(params, "intraday_previous_volume_window")
    recent_high = max(float(bar.high) for bar in bars[-recent_high_window:]) if bars else float(latest.high)
    previous_high = max((float(bar.high) for bar in bars[:-1]), default=recent_high)
    recent_closes = [float(bar.close) for bar in bars[-close_window:]]
    recent_volumes = [float(bar.volume) for bar in bars[-recent_volume_window:]]
    previous_volumes = [float(bar.volume) for bar in bars[-(previous_volume_window + recent_volume_window):-recent_volume_window]]
    recent_volume_avg = sum(recent_volumes) / max(len(recent_volumes), 1)
    previous_volume_avg = sum(previous_volumes) / max(len(previous_volumes), 1) if previous_volumes else 0.0
    volume_expansion = (
        recent_volume_avg >= previous_volume_avg * _float_param(params, "intraday_volume_expansion_multiplier")
        if previous_volumes
        else False
    )
    close_band = (
        (max(recent_closes) - min(recent_closes)) / max(abs(quote.last_price), _float_param(params, "denominator_floor"))
        if recent_closes
        else 0.0
    )
    false_breakout_flag = (
        recent_high >= max(previous_high, vwap_value) * _float_param(params, "intraday_false_breakout_high_multiplier")
        and quote.last_price < recent_high * _float_param(params, "intraday_false_breakout_retrace_multiplier")
        and quote.last_price < vwap_value * _float_param(params, "intraday_false_breakout_vwap_multiplier")
        and candle.weak_close
    )
    stall_after_volume_flag = (
        volume_expansion
        and close_band <= _float_param(params, "intraday_close_band_max")
        and recent_high >= quote.last_price * _float_param(params, "intraday_stall_high_multiplier")
        and quote.last_price <= max(recent_closes) * _float_param(params, "intraday_stall_close_multiplier")
    )
    intraday_reversal_flag = (
        candle.long_upper_shadow
        and candle.weak_close
        and quote.last_price < vwap_value * _float_param(params, "intraday_reversal_vwap_multiplier")
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
            params=params,
        ),
    )


def _distribution_risk_score(
    *,
    false_breakout_flag: bool,
    stall_after_volume_flag: bool,
    intraday_reversal_flag: bool,
    upper_shadow_ratio: float,
    weak_close: bool,
    params: dict[str, object] | None = None,
) -> float:
    params = params or _params()
    score = 0.0
    if false_breakout_flag:
        score += _float_param(params, "score_false_breakout")
    if stall_after_volume_flag:
        score += _float_param(params, "score_stall_after_volume")
    if intraday_reversal_flag:
        score += _float_param(params, "score_intraday_reversal")
    score += min(
        upper_shadow_ratio * _float_param(params, "score_upper_shadow_weight"),
        _float_param(params, "score_upper_shadow_cap"),
    )
    if weak_close:
        score += _float_param(params, "score_weak_close")
    return round(min(score, _float_param(params, "score_cap")), 2)


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


def _params() -> dict[str, object]:
    from app.services.quant.runtime_parameters import get_market_distribution_signals

    values = get_market_distribution_signals()
    return (
        {**MARKET_DISTRIBUTION_SIGNAL_DEFAULTS, **values}
        if isinstance(values, dict)
        else dict(MARKET_DISTRIBUTION_SIGNAL_DEFAULTS)
    )


def _float_param(params: dict[str, object], key: str) -> float:
    try:
        return float(params.get(key, MARKET_DISTRIBUTION_SIGNAL_DEFAULTS[key]))
    except (KeyError, TypeError, ValueError):
        return float(MARKET_DISTRIBUTION_SIGNAL_DEFAULTS[key])


def _int_param(params: dict[str, object], key: str) -> int:
    return max(1, int(round(_float_param(params, key))))
