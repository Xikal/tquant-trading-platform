from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.low_buy.intraday_confirmation import calculate_intraday_vwap
from app.services.paper.quote_quality import PaperQuotePrice


@dataclass(frozen=True)
class PaperExitContext:
    vwap: float = 0.0
    above_vwap: bool = False
    reclaimed_vwap: bool = False
    vwap_hold: bool = False
    low_rising: bool = False
    intraday_usable: bool = False
    volume_release_ratio: float = 0.0
    volume_usable: bool = False
    high_pullback_ratio: float = 0.0
    high_pullback_pct: float = 0.0
    day_change_pct: float = 0.0
    reason: str = "分时数据不足，按静态持仓规则处理。"


def build_exit_context(quote: PaperQuotePrice | None, bars: list[Any] | None) -> PaperExitContext:
    price = float(getattr(quote, "price", 0.0) or 0.0)
    cleaned_bars = list(bars or [])
    if price <= 0 or len(cleaned_bars) < 5:
        return PaperExitContext(day_change_pct=float(getattr(quote, "change_pct", 0.0) or 0.0))

    vwap = calculate_intraday_vwap(cleaned_bars)
    latest = cleaned_bars[-1]
    latest_close = _bar_value(latest, "close") or price
    if vwap <= 0 or latest_close <= 0:
        return PaperExitContext(day_change_pct=float(getattr(quote, "change_pct", 0.0) or 0.0))

    recent = cleaned_bars[-5:]
    above_vwap = latest_close >= vwap * 0.998
    reclaimed_vwap = _reclaimed_vwap(recent, vwap)
    low_rising = _recent_lows_are_rising(recent)
    vwap_hold = above_vwap and low_rising
    volume_release_ratio, volume_usable = _volume_release_ratio(cleaned_bars)
    high_price = max(float(getattr(quote, "high_price", 0.0) or 0.0), max(_bar_value(item, "high") for item in cleaned_bars))
    low_candidates = [float(getattr(quote, "low_price", 0.0) or 0.0), *[_bar_value(item, "low") for item in cleaned_bars]]
    valid_lows = [value for value in low_candidates if value > 0]
    low_price = min(valid_lows) if valid_lows else latest_close
    intraday_range = max(high_price - low_price, 0.0)
    high_pullback_ratio = (high_price - latest_close) / intraday_range if intraday_range > 0 else 0.0
    prev_close = float(getattr(quote, "prev_close", 0.0) or 0.0)
    high_pullback_pct = (high_price - latest_close) / prev_close * 100 if prev_close > 0 else 0.0
    day_change_pct = float(getattr(quote, "change_pct", 0.0) or 0.0)
    return PaperExitContext(
        vwap=round(vwap, 4),
        above_vwap=above_vwap,
        reclaimed_vwap=reclaimed_vwap,
        vwap_hold=vwap_hold,
        low_rising=low_rising,
        intraday_usable=True,
        volume_release_ratio=round(volume_release_ratio, 4),
        volume_usable=volume_usable,
        high_pullback_ratio=round(max(high_pullback_ratio, 0.0), 4),
        high_pullback_pct=round(max(high_pullback_pct, 0.0), 4),
        day_change_pct=round(day_change_pct, 4),
        reason=_context_reason(above_vwap, reclaimed_vwap, vwap_hold, volume_release_ratio, volume_usable, high_pullback_ratio),
    )


def _bar_value(bar: Any, field: str) -> float:
    return float(getattr(bar, field, 0.0) or 0.0)


def _reclaimed_vwap(bars: list[Any], vwap: float) -> bool:
    closes = [_bar_value(item, "close") for item in bars if _bar_value(item, "close") > 0]
    return len(closes) >= 3 and min(closes[:-1]) < vwap * 0.998 <= closes[-1]


def _recent_lows_are_rising(bars: list[Any]) -> bool:
    lows = [_bar_value(item, "low") for item in bars if _bar_value(item, "low") > 0]
    if len(lows) < 3:
        return False
    return lows[-1] >= min(lows[-3:-1]) * 0.998 and lows[-2] >= lows[0] * 0.996


def _volume_release_ratio(bars: list[Any]) -> tuple[float, bool]:
    volumes = [_bar_value(item, "volume") for item in bars if _bar_value(item, "volume") >= 0]
    if len(volumes) < 8:
        return 0.0, False
    recent_avg = sum(volumes[-3:]) / 3
    base = volumes[-23:-3] if len(volumes) >= 23 else volumes[:-3]
    base_avg = sum(base) / max(len(base), 1)
    return (recent_avg / base_avg, True) if base_avg > 0 else (0.0, False)


def _context_reason(
    above_vwap: bool,
    reclaimed_vwap: bool,
    vwap_hold: bool,
    volume_ratio: float,
    volume_usable: bool,
    pullback_ratio: float,
) -> str:
    if not above_vwap:
        return "价格弱于分时均价线，先按防守处理。"
    if not volume_usable:
        return "分时量能样本不足，仅参考价格结构。"
    if pullback_ratio >= 0.45 and volume_ratio < 0.8:
        return "冲高后回落且量能没有释放，优先保护利润。"
    if vwap_hold:
        return "价格在分时均价线上方，低点仍有承接。"
    if reclaimed_vwap:
        return "价格重新站回分时均价线，疑似洗盘修复。"
    return "价格暂在分时均价线上方，但承接确认还不充分。"
