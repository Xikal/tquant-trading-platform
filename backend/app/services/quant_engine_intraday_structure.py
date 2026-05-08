from __future__ import annotations

from dataclasses import dataclass

from app.models.schemas import KlineBar, QuoteSnapshot
from app.services.distribution_signals import DistributionSnapshot
from app.services.market.parameter_defaults import POSITION_T_INTRADAY_STRUCTURE_DEFAULTS


@dataclass(frozen=True)
class IntradayStructureSnapshot:
    key: str
    text: str


def classify_intraday_structure(
    *,
    quote: QuoteSnapshot,
    bars: list[KlineBar],
    ma5: float,
    vwap_value: float,
    distribution: DistributionSnapshot,
) -> IntradayStructureSnapshot:
    params = _params()
    if len(bars) < _int_param(params, "min_bars") or quote.last_price <= 0 or vwap_value <= 0 or ma5 <= 0:
        return IntradayStructureSnapshot("insufficient_intraday", "分时数据不足，不能确认做T结构")

    recent_window = _int_param(params, "recent_window")
    previous_window = _int_param(params, "previous_window")
    recent = bars[-recent_window:]
    previous = bars[-(recent_window + previous_window):-recent_window] or bars[:-recent_window]
    anchor = min(ma5, vwap_value)
    pulled_back = min(bar.low for bar in recent) <= anchor * _float_param(params, "pullback_anchor_multiplier")
    reclaimed_vwap = quote.last_price >= vwap_value * _float_param(params, "reclaim_vwap_multiplier")
    lows_rising = _lows_are_rising(recent[-4:], params=params)
    volume_shrunk = _avg_volume(recent[-4:-1], params=params) <= _avg_volume(previous, params=params) * _float_param(params, "volume_shrink_multiplier")
    if pulled_back and reclaimed_vwap and lows_rising and volume_shrunk:
        return IntradayStructureSnapshot("pullback_acceptance", "回踩承接：回踩 VWAP/MA5 后重新站回，低点抬高且量能收缩")

    if distribution.false_breakout_flag:
        return IntradayStructureSnapshot("false_breakout", "假突破：冲高后跌回关键位，优先防守")
    if _overheat_exhaustion(quote=quote, ma5=ma5, vwap_value=vwap_value, distribution=distribution, params=params):
        return IntradayStructureSnapshot("overheat_exhaustion", "冲高衰竭：价格偏离均价且上方抛压增强")
    if distribution.stall_after_volume_flag:
        return IntradayStructureSnapshot("volume_stall", "放量滞涨：量能放大但价格扩张不足")
    if _sharp_drop_repair(quote=quote, recent=recent, vwap_value=vwap_value, params=params):
        return IntradayStructureSnapshot("sharp_drop_repair", "急跌修复：快速跌破后收回 VWAP，但还需继续确认")
    if _range_contraction(quote=quote, recent=recent, previous=previous, params=params):
        return IntradayStructureSnapshot("range_contraction", "缩量横盘：波动和成交收敛，暂不主动做T")
    return IntradayStructureSnapshot("balanced_intraday", "均衡分时：没有明确承接或衰竭结构")


def _lows_are_rising(bars: list[KlineBar], *, params: dict[str, object] | None = None) -> bool:
    params = params or _params()
    if len(bars) < _int_param(params, "rising_lows_min_bars"):
        return False
    lows = [bar.low for bar in bars]
    return lows[-1] >= lows[-2] >= min(lows[0], lows[1])


def _avg_volume(bars: list[KlineBar], *, params: dict[str, object] | None = None) -> float:
    params = params or _params()
    if not bars:
        return _float_param(params, "avg_volume_floor")
    return max(sum(max(bar.volume, 0.0) for bar in bars) / len(bars), _float_param(params, "avg_volume_floor"))


def _overheat_exhaustion(
    *,
    quote: QuoteSnapshot,
    ma5: float,
    vwap_value: float,
    distribution: DistributionSnapshot,
    params: dict[str, object],
) -> bool:
    near_intraday_high = quote.high_price > 0 and quote.last_price >= quote.high_price * _float_param(params, "near_high_multiplier")
    extended = quote.last_price >= max(
        ma5 * _float_param(params, "extended_ma5_multiplier"),
        vwap_value * _float_param(params, "extended_vwap_multiplier"),
    )
    pressure = (
        distribution.long_upper_shadow
        or distribution.weak_close
        or distribution.distribution_risk_score >= _float_param(params, "pressure_distribution_risk_min")
    )
    return near_intraday_high and extended and pressure


def _sharp_drop_repair(
    *,
    quote: QuoteSnapshot,
    recent: list[KlineBar],
    vwap_value: float,
    params: dict[str, object],
) -> bool:
    if not recent:
        return False
    pierced_vwap = min(bar.low for bar in recent) <= vwap_value * _float_param(params, "sharp_drop_vwap_break_multiplier")
    reclaimed = quote.last_price >= vwap_value * _float_param(params, "sharp_drop_reclaim_multiplier")
    return pierced_vwap and reclaimed and _lows_are_rising(recent[-4:], params=params)


def _range_contraction(
    *,
    quote: QuoteSnapshot,
    recent: list[KlineBar],
    previous: list[KlineBar],
    params: dict[str, object],
) -> bool:
    if len(recent) < _int_param(params, "range_contraction_min_bars"):
        return False
    recent_range = max(
        max(bar.high for bar in recent) - min(bar.low for bar in recent),
        _float_param(params, "range_floor"),
    )
    day_range = max(quote.high_price - quote.low_price, _float_param(params, "range_floor"))
    return (
        recent_range <= day_range * _float_param(params, "range_contraction_day_range_multiplier")
        and _avg_volume(recent, params=params) <= _avg_volume(previous, params=params) * _float_param(params, "range_contraction_volume_multiplier")
    )


def _params() -> dict[str, object]:
    from app.services.quant.runtime_parameters import get_position_t_intraday_structure

    values = get_position_t_intraday_structure()
    return (
        {**POSITION_T_INTRADAY_STRUCTURE_DEFAULTS, **values}
        if isinstance(values, dict)
        else dict(POSITION_T_INTRADAY_STRUCTURE_DEFAULTS)
    )


def _float_param(params: dict[str, object], key: str) -> float:
    try:
        return float(params.get(key, POSITION_T_INTRADAY_STRUCTURE_DEFAULTS[key]))
    except (KeyError, TypeError, ValueError):
        return float(POSITION_T_INTRADAY_STRUCTURE_DEFAULTS[key])


def _int_param(params: dict[str, object], key: str) -> int:
    return max(1, int(round(_float_param(params, key))))
