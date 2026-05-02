from __future__ import annotations

from app.services.low_buy.positioning import build_position_breakdown_text
from app.services.low_buy.shared import Any, LowBuyCandidateOut, pd


def build_signal_update(
    candidate: LowBuyCandidateOut,
    state: str,
    text: str,
    hint: str,
    entry_distance: float,
    position_resolver,
    confirmed_trade_date: str | None = None,
) -> LowBuyCandidateOut:
    position_pct, position_text = position_resolver(candidate, state)
    update = {
        "buy_signal_state": state,
        "buy_signal_text": text,
        "buy_signal_hint": hint,
        "entry_distance_pct": entry_distance,
        "suggested_position_pct": position_pct,
        "suggested_position_text": position_text,
        "position_breakdown_text": _position_breakdown_text(candidate, position_pct),
    }
    if confirmed_trade_date:
        update["confirmed_trade_date"] = confirmed_trade_date
    return candidate.model_copy(update=update)


def _position_breakdown_text(candidate: LowBuyCandidateOut, position_pct: float) -> str:
    if position_pct <= 0:
        return ""
    return build_position_breakdown_text(candidate, position_pct)


def intraday_soft_confirmation(
    candidate: LowBuyCandidateOut,
    quote: Any | None = None,
    *,
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
    low_price = float(getattr(quote, "low_price", 0.0) or 0.0)
    high_price = float(getattr(quote, "high_price", 0.0) or 0.0)
    change_pct = float(getattr(quote, "change_pct", 0.0) or 0.0)
    if last_price <= 0 or low_price <= 0 or last_price <= candidate.stop_loss * 1.01 or change_pct <= -5.8:
        return False
    intraday_range = max(high_price - low_price, 0.01)
    rebound_ratio = (last_price - low_price) / intraday_range
    if rebound_ratio < 0.26:
        return False
    if open_price > 0 and last_price < open_price * 0.99:
        return False
    if intraday_bars:
        return _minute_reclaim_confirmation(
            candidate=candidate,
            intraday_bars=intraday_bars,
            vwap_value=vwap_value,
        )
    return True


def _minute_reclaim_confirmation(
    *,
    candidate: LowBuyCandidateOut,
    intraday_bars: list[Any],
    vwap_value: float,
) -> bool:
    recent_bars = intraday_bars[-5:]
    if len(recent_bars) < 3:
        return False
    latest = recent_bars[-1]
    last_close = float(getattr(latest, "close", 0.0) or 0.0)
    if last_close <= 0:
        return False
    recent_lows = [float(getattr(item, "low", 0.0) or 0.0) for item in recent_bars]
    recent_volumes = [float(getattr(item, "volume", 0.0) or 0.0) for item in recent_bars]
    valid_lows = [value for value in recent_lows if value > 0]
    if not valid_lows:
        return False
    recent_min_low = min(valid_lows)
    if recent_min_low <= candidate.stop_loss * 1.004:
        return False
    higher_lows = _recent_lows_are_stabilizing(recent_lows)
    reclaimed_vwap = vwap_value > 0 and last_close >= vwap_value * 0.998
    reclaimed_entry = recent_min_low <= candidate.entry_zone_high and last_close >= candidate.entry_zone_low * 0.998
    latest_volume = recent_volumes[-1]
    previous_volume_avg = sum(recent_volumes[:-1]) / max(len(recent_volumes) - 1, 1)
    bullish_bar = (
        last_close >= float(getattr(latest, "open", last_close) or last_close)
        and latest_volume >= previous_volume_avg * 0.75
    )
    return (reclaimed_vwap or reclaimed_entry) and (higher_lows or bullish_bar)


def _recent_lows_are_stabilizing(lows: list[float]) -> bool:
    valid_lows = [value for value in lows if value > 0]
    if len(valid_lows) < 3:
        return False
    latest_lows = valid_lows[-3:]
    return latest_lows[-1] >= min(latest_lows[:-1]) * 0.998 and latest_lows[-2] >= valid_lows[0] * 0.996


def end_of_day_soft_confirmation(candidate: LowBuyCandidateOut, latest_bar: pd.Series) -> bool:
    close_price = float(latest_bar["close"])
    open_price = float(latest_bar["open"])
    low_price = float(latest_bar["low"])
    high_price = float(latest_bar["high"])
    pct_chg = float(latest_bar["pct_chg"])
    if close_price <= candidate.stop_loss * 1.01 or pct_chg <= -5.8:
        return False
    intraday_range = max(high_price - low_price, 0.01)
    rebound_ratio = (close_price - low_price) / intraday_range
    return rebound_ratio >= 0.26 and close_price >= open_price * 0.99
