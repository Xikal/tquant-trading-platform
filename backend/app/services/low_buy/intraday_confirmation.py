from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from typing import Any

VWAP_CONFIRMATION_STRATEGIES = {
    "core_midcap_vwap_ma5_retrace",
    "sector_mainline_first_divergence_low_buy",
    "mainline_limitup_shrink_retrace_reclaim",
}
LATE_SESSION_CONFIRMATION_STRATEGIES = {"late_session_strong_support"}


@dataclass(frozen=True)
class IntradayConfirmation:
    vwap: float = 0.0
    above_vwap: bool = False
    reclaimed_vwap: bool = False
    vwap_hold: bool = False
    low_rising: bool = False
    bullish_reclaim: bool = False
    late_session_strength: bool = False
    late_session_above_vwap: bool = False
    usable: bool = False
    reason: str = "缺少分时数据，不能做盘中确认。"

    @property
    def confirmed(self) -> bool:
        return self.vwap_hold or self.reclaimed_vwap or self.bullish_reclaim

    @property
    def late_confirmed(self) -> bool:
        return self.late_session_strength and self.late_session_above_vwap


def build_intraday_confirmation(intraday_bars: list[Any] | None) -> IntradayConfirmation:
    bars = list(intraday_bars or [])
    if len(bars) < 5:
        return IntradayConfirmation()
    vwap_value = calculate_intraday_vwap(bars)
    if vwap_value <= 0:
        return IntradayConfirmation(reason="分时均价不可用，不能做盘中确认。")

    recent_bars = bars[-5:]
    latest = recent_bars[-1]
    latest_close = _bar_value(latest, "close")
    latest_open = _bar_value(latest, "open")
    if latest_close <= 0:
        return IntradayConfirmation(vwap=vwap_value, usable=False, reason="最新分时收盘价不可用。")

    above_vwap = latest_close >= vwap_value * 0.998
    low_rising = _recent_lows_are_rising(recent_bars)
    reclaimed_vwap = _reclaimed_vwap(recent_bars, vwap_value)
    vwap_hold = above_vwap and low_rising
    bullish_reclaim = (
        above_vwap
        and latest_close >= max(latest_open, vwap_value) * 0.998
        and _latest_volume_not_weak(recent_bars)
    )
    late_strength, late_above_vwap = _late_session_confirmation(bars, vwap_value)

    reason = _reason_text(
        above_vwap=above_vwap,
        reclaimed_vwap=reclaimed_vwap,
        vwap_hold=vwap_hold,
        low_rising=low_rising,
        late_session_strength=late_strength,
        late_session_above_vwap=late_above_vwap,
    )
    return IntradayConfirmation(
        vwap=vwap_value,
        above_vwap=above_vwap,
        reclaimed_vwap=reclaimed_vwap,
        vwap_hold=vwap_hold,
        low_rising=low_rising,
        bullish_reclaim=bullish_reclaim,
        late_session_strength=late_strength,
        late_session_above_vwap=late_above_vwap,
        usable=True,
        reason=reason,
    )


def strategy_requires_intraday_confirmation(strategy_key: str) -> bool:
    return strategy_key in VWAP_CONFIRMATION_STRATEGIES or strategy_key in LATE_SESSION_CONFIRMATION_STRATEGIES


def intraday_confirmation_passes(strategy_key: str, confirmation: IntradayConfirmation) -> bool:
    if strategy_key in VWAP_CONFIRMATION_STRATEGIES:
        return confirmation.confirmed
    if strategy_key in LATE_SESSION_CONFIRMATION_STRATEGIES:
        return confirmation.late_confirmed or confirmation.confirmed
    return True


def intraday_confirmation_hint(strategy_key: str, confirmation: IntradayConfirmation) -> str:
    if not strategy_requires_intraday_confirmation(strategy_key):
        return ""
    if not confirmation.usable:
        return confirmation.reason
    if intraday_confirmation_passes(strategy_key, confirmation):
        return confirmation.reason
    if strategy_key in LATE_SESSION_CONFIRMATION_STRATEGIES:
        return "收盘承接策略需要分时均价上方运行或尾盘不转弱；当前承接还不够。"
    return "需要重新站回分时均价并出现低点抬高；当前只保留观察。"


def _bar_value(bar: Any, field: str) -> float:
    return float(getattr(bar, field, 0.0) or 0.0)


def calculate_intraday_vwap(bars: list[Any] | None) -> float:
    """Use成交额/成交量优先，缺失时再退回典型价格近似。"""
    total_turnover = 0.0
    total_volume = 0.0
    for bar in bars or []:
        volume = _bar_value(bar, "volume")
        if volume <= 0:
            continue
        amount_turnover = _normalized_amount_turnover(bar, volume)
        if amount_turnover > 0:
            total_turnover += amount_turnover
            total_volume += volume
            continue
        typical_price = _typical_price(bar)
        if typical_price > 0:
            total_turnover += typical_price * volume
            total_volume += volume
    if total_volume > 0:
        return round(total_turnover / total_volume, 4)
    return 0.0


def _normalized_amount_turnover(bar: Any, volume: float) -> float:
    amount = _bar_value(bar, "amount")
    if amount <= 0 or volume <= 0:
        return 0.0
    typical_price = _typical_price(bar)
    if typical_price <= 0:
        return amount
    raw_price = amount / volume
    if raw_price > typical_price * 20:
        return amount / 100
    if raw_price < typical_price / 20:
        return amount * 100
    return amount


def _typical_price(bar: Any) -> float:
    high = _bar_value(bar, "high")
    low = _bar_value(bar, "low")
    close = _bar_value(bar, "close")
    if high <= 0 or low <= 0 or close <= 0:
        return 0.0
    return (high + low + close) / 3


def _recent_lows_are_rising(bars: list[Any]) -> bool:
    lows = [_bar_value(bar, "low") for bar in bars if _bar_value(bar, "low") > 0]
    if len(lows) < 3:
        return False
    latest_lows = lows[-3:]
    return latest_lows[-1] >= min(latest_lows[:-1]) * 0.998 and latest_lows[-2] >= lows[0] * 0.996


def _reclaimed_vwap(bars: list[Any], vwap_value: float) -> bool:
    closes = [_bar_value(bar, "close") for bar in bars if _bar_value(bar, "close") > 0]
    if len(closes) < 3:
        return False
    return min(closes[:-1]) < vwap_value * 0.998 and closes[-1] >= vwap_value * 0.998


def _latest_volume_not_weak(bars: list[Any]) -> bool:
    volumes = [_bar_value(bar, "volume") for bar in bars]
    if len(volumes) < 3:
        return False
    previous_avg = sum(volumes[:-1]) / max(len(volumes) - 1, 1)
    return volumes[-1] >= previous_avg * 0.72


def _late_session_confirmation(bars: list[Any], vwap_value: float) -> tuple[bool, bool]:
    late_bars = [bar for bar in bars if _is_late_session(getattr(bar, "timestamp", ""))]
    if len(late_bars) < 3:
        return False, False
    latest_close = _bar_value(late_bars[-1], "close")
    if latest_close <= 0:
        return False, False
    late_high = max(_bar_value(bar, "high") for bar in late_bars)
    late_lows = [_bar_value(bar, "low") for bar in late_bars if _bar_value(bar, "low") > 0]
    if not late_lows:
        return False, False
    late_low = min(late_lows)
    late_range = max(late_high - late_low, 0.01)
    close_position = (latest_close - late_low) / late_range
    late_strength = close_position >= 0.52 and latest_close >= _bar_value(late_bars[0], "open") * 0.995
    return late_strength, latest_close >= vwap_value * 0.998


def _is_late_session(timestamp: str) -> bool:
    parsed = _parse_timestamp(timestamp)
    if parsed is None:
        return False
    return parsed.time() >= time(14, 30)


def _parse_timestamp(timestamp: str) -> datetime | None:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%H:%M:%S", "%H:%M"):
        try:
            parsed = datetime.strptime(timestamp, fmt)
            if fmt.startswith("%H"):
                return datetime.combine(datetime.today().date(), parsed.time())
            return parsed
        except ValueError:
            continue
    return None


def _reason_text(
    *,
    above_vwap: bool,
    reclaimed_vwap: bool,
    vwap_hold: bool,
    low_rising: bool,
    late_session_strength: bool,
    late_session_above_vwap: bool,
) -> str:
    if late_session_strength and late_session_above_vwap:
        return "尾盘运行在分时均价上方，收盘承接正常。"
    if vwap_hold:
        return "价格在分时均价上方，近几根分时低点抬高。"
    if reclaimed_vwap:
        return "价格已重新站回分时均价，盘中承接正在恢复。"
    if above_vwap:
        return "价格暂在分时均价上方，但低点抬高还不充分。"
    if low_rising:
        return "分时低点有抬高，但尚未站回分时均价。"
    return "价格仍弱于分时均价，盘中确认不足。"
