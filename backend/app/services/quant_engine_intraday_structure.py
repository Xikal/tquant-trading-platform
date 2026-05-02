from __future__ import annotations

from dataclasses import dataclass

from app.models.schemas import KlineBar, QuoteSnapshot
from app.services.distribution_signals import DistributionSnapshot


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
    if len(bars) < 6 or quote.last_price <= 0 or vwap_value <= 0 or ma5 <= 0:
        return IntradayStructureSnapshot("insufficient_intraday", "分时数据不足，不能确认做T结构")

    recent = bars[-5:]
    previous = bars[-10:-5] or bars[:-5]
    anchor = min(ma5, vwap_value)
    pulled_back = min(bar.low for bar in recent) <= anchor * 1.004
    reclaimed_vwap = quote.last_price >= vwap_value * 1.001
    lows_rising = _lows_are_rising(recent[-4:])
    volume_shrunk = _avg_volume(recent[-4:-1]) <= _avg_volume(previous) * 0.96
    if pulled_back and reclaimed_vwap and lows_rising and volume_shrunk:
        return IntradayStructureSnapshot("pullback_acceptance", "回踩承接：回踩 VWAP/MA5 后重新站回，低点抬高且量能收缩")

    if distribution.false_breakout_flag:
        return IntradayStructureSnapshot("false_breakout", "假突破：冲高后跌回关键位，优先防守")
    if _overheat_exhaustion(quote=quote, ma5=ma5, vwap_value=vwap_value, distribution=distribution):
        return IntradayStructureSnapshot("overheat_exhaustion", "冲高衰竭：价格偏离均价且上方抛压增强")
    if distribution.stall_after_volume_flag:
        return IntradayStructureSnapshot("volume_stall", "放量滞涨：量能放大但价格扩张不足")
    if _sharp_drop_repair(quote=quote, recent=recent, vwap_value=vwap_value):
        return IntradayStructureSnapshot("sharp_drop_repair", "急跌修复：快速跌破后收回 VWAP，但还需继续确认")
    if _range_contraction(quote=quote, recent=recent, previous=previous):
        return IntradayStructureSnapshot("range_contraction", "缩量横盘：波动和成交收敛，暂不主动做T")
    return IntradayStructureSnapshot("balanced_intraday", "均衡分时：没有明确承接或衰竭结构")


def _lows_are_rising(bars: list[KlineBar]) -> bool:
    if len(bars) < 3:
        return False
    lows = [bar.low for bar in bars]
    return lows[-1] >= lows[-2] >= min(lows[0], lows[1])


def _avg_volume(bars: list[KlineBar]) -> float:
    if not bars:
        return 1.0
    return max(sum(max(bar.volume, 0.0) for bar in bars) / len(bars), 1.0)


def _overheat_exhaustion(
    *,
    quote: QuoteSnapshot,
    ma5: float,
    vwap_value: float,
    distribution: DistributionSnapshot,
) -> bool:
    near_intraday_high = quote.high_price > 0 and quote.last_price >= quote.high_price * 0.985
    extended = quote.last_price >= max(ma5 * 1.01, vwap_value * 1.008)
    pressure = distribution.long_upper_shadow or distribution.weak_close or distribution.distribution_risk_score >= 4.8
    return near_intraday_high and extended and pressure


def _sharp_drop_repair(
    *,
    quote: QuoteSnapshot,
    recent: list[KlineBar],
    vwap_value: float,
) -> bool:
    if not recent:
        return False
    pierced_vwap = min(bar.low for bar in recent) <= vwap_value * 0.988
    reclaimed = quote.last_price >= vwap_value * 1.002
    return pierced_vwap and reclaimed and _lows_are_rising(recent[-4:])


def _range_contraction(
    *,
    quote: QuoteSnapshot,
    recent: list[KlineBar],
    previous: list[KlineBar],
) -> bool:
    if len(recent) < 3:
        return False
    recent_range = max(max(bar.high for bar in recent) - min(bar.low for bar in recent), 0.01)
    day_range = max(quote.high_price - quote.low_price, 0.01)
    return recent_range <= day_range * 0.28 and _avg_volume(recent) <= _avg_volume(previous) * 0.9
