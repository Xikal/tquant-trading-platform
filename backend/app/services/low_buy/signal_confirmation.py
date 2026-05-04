from __future__ import annotations

from app.services.low_buy.signal_helpers import recent_intraday_distribution
from app.services.low_buy.signal_resolution import intraday_soft_confirmation
from app.services.low_buy.intraday_confirmation import calculate_intraday_vwap
from app.services.low_buy.shared import Any, LowBuyCandidateOut, pd


def is_intraday_stop_confirmed(
    *,
    candidate: LowBuyCandidateOut,
    quote: Any | None = None,
    intraday_bars: list[Any] | None = None,
    vwap_value: float = 0.0,
    require_intraday_structure: bool = False,
) -> bool:
    if quote is None:
        return False
    if require_intraday_structure and not intraday_bars:
        return False
    last_price = float(getattr(quote, "last_price", 0.0) or 0.0)
    open_price = float(getattr(quote, "open_price", 0.0) or 0.0)
    prev_close = float(getattr(quote, "prev_close", 0.0) or 0.0)
    low_price = float(getattr(quote, "low_price", 0.0) or 0.0)
    high_price = float(getattr(quote, "high_price", 0.0) or 0.0)
    change_pct = float(getattr(quote, "change_pct", 0.0) or 0.0)
    if last_price <= 0 or low_price <= 0 or last_price <= candidate.stop_loss * 1.006 or change_pct <= -6.5:
        return False
    intraday_range = max(high_price - low_price, 0.01)
    rebound_ratio = (last_price - low_price) / intraday_range
    held_reference = True
    if open_price > 0:
        held_reference = held_reference and last_price >= open_price * 0.995
    if prev_close > 0:
        held_reference = held_reference and last_price >= prev_close * 0.982
    if rebound_ratio < 0.35 or not held_reference:
        return False
    if intraday_bars:
        if vwap_value <= 0:
            vwap_value = calculate_intraday_vwap(intraday_bars)
        return intraday_soft_confirmation(
            candidate,
            quote,
            intraday_bars=intraday_bars,
            vwap_value=vwap_value,
            require_intraday_structure=require_intraday_structure,
        )
    return True


def is_end_of_day_stop_confirmed(candidate: LowBuyCandidateOut, latest_bar: pd.Series) -> bool:
    close_price = float(latest_bar["close"])
    open_price = float(latest_bar["open"])
    low_price = float(latest_bar["low"])
    high_price = float(latest_bar["high"])
    pct_chg = float(latest_bar["pct_chg"])
    if close_price <= candidate.stop_loss * 1.006 or pct_chg <= -6.5:
        return False
    intraday_range = max(high_price - low_price, 0.01)
    rebound_ratio = (close_price - low_price) / intraday_range
    return rebound_ratio >= 0.35 and close_price >= open_price * 0.995


def intraday_daily_signal_veto(
    *,
    candidate: LowBuyCandidateOut,
    quote: Any | None,
    intraday_bars: list[Any] | None,
    vwap_value: float,
) -> str:
    if quote is None:
        return ""
    last_price = float(getattr(quote, "last_price", 0.0) or 0.0)
    open_price = float(getattr(quote, "open_price", 0.0) or 0.0)
    volume_ratio = float(getattr(quote, "volume_ratio", 0.0) or 0.0)
    if last_price <= 0:
        return ""
    if volume_ratio >= 2.2 and open_price > 0 and last_price < open_price * 0.995:
        return "盘中放量但价格跌回开盘价下方，日线缩量承接口径已走坏，今日不执行。"
    if intraday_bars and recent_intraday_distribution(intraday_bars, vwap_value):
        return "盘中最近几根分时放量走弱，没有守住分时均价，否决日线候选信号。"
    return ""
