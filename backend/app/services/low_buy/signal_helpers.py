from __future__ import annotations

from app.services.low_buy.shared import Any, LowBuyCandidateOut


def is_hot_frontline_candidate(candidate: LowBuyCandidateOut) -> bool:
    return (
        candidate.leader_rank in {"leader", "strong_follow"}
        and candidate.industry_tier in {"core_hot", "secondary_hot"}
    )


def recent_intraday_distribution(intraday_bars: list[Any], vwap_value: float) -> bool:
    recent = list(intraday_bars or [])[-5:]
    if len(recent) < 4:
        return False
    latest = recent[-1]
    latest_close = bar_float(latest, "close")
    latest_open = bar_float(latest, "open")
    if latest_close <= 0:
        return False
    volumes = [bar_float(bar, "volume") for bar in recent]
    previous_avg = sum(volumes[:-1]) / max(len(volumes) - 1, 1)
    latest_volume_expanded = volumes[-1] >= max(previous_avg, 1.0) * 1.55
    below_vwap = vwap_value > 0 and latest_close < vwap_value * 0.998
    weak_bar = latest_close < latest_open * 0.998
    lows = [bar_float(bar, "low") for bar in recent if bar_float(bar, "low") > 0]
    lower_low = len(lows) >= 3 and lows[-1] < min(lows[:-1]) * 0.998
    return latest_volume_expanded and (below_vwap or weak_bar or lower_low)


def bar_float(bar: Any, field: str) -> float:
    return float(getattr(bar, field, 0.0) or 0.0)


def buy_now_hint(entry_position: str, historical: bool, soft: bool) -> str:
    if soft:
        if historical:
            return "收盘价已进入买点区，软确认成立，可按轻仓试错处理。"
        if entry_position == "near_above_zone":
            return "价格接近买点区上沿且软确认成立，可先轻仓试错，强确认后再补。"
        return "价格已进入买点区，软确认成立，可先轻仓试错，强确认后再补。"
    if historical:
        return "收盘价已进入买点区，且日线止跌确认成立。" if entry_position == "in_zone" else "收盘价已经跌入并略穿买点区，但日线止跌确认成立。"
    return "价格已进入买点区，且日内止跌确认基本成立，可按 2-3 成仓分批试仓，跌破止损位离场。" if entry_position == "in_zone" else "价格已经跌入并略穿买点区，但承接已企稳，可按 3-4 成仓分批试仓，跌破止损位离场。"


def strict_strategy_avoid_hint(entry_position: str, historical: bool) -> str:
    if entry_position == "below_stop":
        return below_stop_hint(historical)
    if historical:
        return "收盘价已跌穿买点区，这类涨停突破回踩不做下方硬接，暂不跟踪。"
    return "价格已跌穿买点区，这类涨停突破回踩只做区间内确认，不做下方硬接。"


def near_entry_hint(entry_position: str, entry_distance: float, historical: bool) -> str:
    if entry_position == "in_zone":
        return "价格到位了，但收盘确认还不够。" if historical else "价格已进入买点区，但日内止跌确认还不够，先等承接稳定。"
    if entry_position == "below_zone":
        return "价格已经跌入并略穿买点区，但收盘确认还不够。" if historical else "价格已经跌入并略穿买点区，但还没止跌确认，不能机械接刀。"
    return f"历史回放里距离买点区上沿只差 {entry_distance:.2f}%。" if historical else f"离买点区上沿只差 {entry_distance:.2f}%，承接确认后可准备试仓。"


def below_stop_hint(historical: bool) -> str:
    return "历史回放里价格已逼近止损线，本次低吸逻辑失效。" if historical else "价格已经逼近或跌破止损线，低吸逻辑失效，今天不再接。"


def restricted_market_avoid_hint(historical: bool) -> str:
    if historical:
        return "历史回放处于弱市场状态，只有高分且贴近买点的票才保留跟踪。"
    return "当前市场偏弱，只保留高分且贴近买点的票；这只暂不进入执行观察。"


def mature_watch_hint(entry_distance: float, historical: bool) -> str:
    return f"历史回放里还没到买点区，距离约 {entry_distance:.2f}%。" if historical else f"结构已经成熟，但当前价距买点区还有 {entry_distance:.2f}%，不追高。"


def structure_pending_hint(entry_position: str, historical: bool) -> str:
    if historical:
        return "历史回放里价格到了买点区，但结构条件还没全部满足。" if entry_position == "in_zone" else "历史回放里价格跌入并略穿买点区，但结构还没成熟。"
    return "价格已经到买点区，但结构条件还没全部满足，先等缩量、承接或趋势确认。" if entry_position == "in_zone" else "价格已经跌入并略穿买点区，但结构还没成熟，不能只因为便宜就买。"
