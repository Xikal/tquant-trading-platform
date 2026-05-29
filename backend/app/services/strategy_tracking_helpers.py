from __future__ import annotations

import json
from datetime import datetime, timezone
from statistics import median
from typing import Any

from app.models.entities import LowBuyResultSnapshot
from app.models.schema_defs.strategy_tracking import (
    StrategyTrackingItemOut,
    StrategyTrackingPerformanceOut,
    StrategyTrackingSummaryOut,
)
from app.repositories.low_buy import DailyBarRow
from app.services.finance.performance_math import sequence_max_drawdown_pct


def load_payload(row: LowBuyResultSnapshot) -> tuple[dict[str, Any], str | None]:
    try:
        payload = json.loads(row.payload_json or "{}")
    except json.JSONDecodeError:
        return {}, "payload_json_invalid"
    return (payload if isinstance(payload, dict) else {}), None


def compact_payload(payload: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "summary_reason",
        "reasons",
        "risks",
        "tags",
        "market_state",
        "market_state_text",
        "market_state_category_text",
        "mainline_tier_text",
        "leader_strength_text",
        "data_quality",
        "data_quality_text",
        "entry_zone_low",
        "entry_zone_high",
        "stop_loss",
        "take_profit",
    }
    return {key: value for key, value in payload.items() if key in allowed}


def posterior_stats(
    bars: list[DailyBarRow],
    *,
    reference_price: float | None,
    entry_low: float | None,
    entry_high: float | None,
    stop_loss: float | None,
    target_price: float | None,
) -> dict[str, Any]:
    if not bars or not reference_price or reference_price <= 0:
        return {
            "current_price": None,
            "current_return_pct": None,
            "max_price": None,
            "max_gain_pct": None,
            "max_drawdown_pct": None,
            "entry_touched": False,
            "stop_triggered": False,
            "stop_triggered_date": None,
            "target_touched": False,
            "target_touched_date": None,
        }
    max_price = max(bar.high_price for bar in bars)
    closes = [reference_price] + [bar.close_price for bar in bars]
    stop_bar = next((bar for bar in bars if stop_loss and bar.low_price <= stop_loss), None)
    target_bar = next((bar for bar in bars if target_price and bar.high_price >= target_price), None)
    return {
        "current_price": bars[-1].close_price,
        "current_return_pct": pct(bars[-1].close_price, reference_price),
        "max_price": max_price,
        "max_gain_pct": pct(max_price, reference_price),
        "max_drawdown_pct": sequence_max_drawdown_pct(closes),
        "entry_touched": any(hit_entry(bar, entry_low, entry_high) for bar in bars),
        "stop_triggered": stop_bar is not None,
        "stop_triggered_date": stop_bar.trade_date if stop_bar else None,
        "target_touched": target_bar is not None,
        "target_touched_date": target_bar.trade_date if target_bar else None,
    }


def item_id(strategy_key: str, symbol: str, first_signal_date: str) -> str:
    return f"{strategy_key}:{symbol}:{first_signal_date}"


def parse_item_id(item_id_value: str) -> tuple[str, str, str]:
    parts = item_id_value.split(":")
    if len(parts) != 3 or not all(parts):
        raise ValueError("策略跟踪记录 ID 格式错误")
    return parts[0], parts[1], parts[2]


def number(payload: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = payload.get(key)
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            continue
        if parsed > 0:
            return parsed
    return None


def text(payload: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def attr_float(owner: Any, field: str) -> float | None:
    value = getattr(owner, field, None) if owner is not None else None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def hit_entry(bar: DailyBarRow, entry_low: float | None, entry_high: float | None) -> bool:
    if not entry_low or not entry_high:
        return False
    return bar.low_price <= entry_high and bar.high_price >= entry_low


def pct(value: float, reference: float) -> float:
    return (value / reference - 1.0) * 100.0 if reference > 0 else 0.0


def round_value(value: float, digits: int = 2) -> float:
    return round(float(value), digits)


def round_or_none(value: float | None) -> float | None:
    return None if value is None else round_value(value)


def avg(values: list[float]) -> float:
    return round_value(sum(values) / len(values)) if values else 0.0


def ratio(numerator: int, denominator: int) -> float:
    return round_value(numerator / denominator * 100.0) if denominator else 0.0


def distance_to_entry(current_price: float | None, entry_low: float | None, entry_high: float | None) -> float | None:
    if current_price is None or not entry_low or not entry_high:
        return None
    if entry_low <= current_price <= entry_high:
        return 0.0
    target = entry_high if current_price > entry_high else entry_low
    return pct(current_price, target)


def win_rate(items: list[StrategyTrackingItemOut], min_days: int) -> float:
    eligible = [item for item in items if item.recommendation_days >= min_days and item.current_return_pct is not None]
    return ratio(sum(1 for item in eligible if (item.current_return_pct or 0.0) > 0), len(eligible))


def resolve_data_quality(*, has_payload_error: bool, bars: list[DailyBarRow], latest_bar_date: str) -> str:
    if has_payload_error:
        return "partial"
    if not bars:
        return "unavailable"
    if any(bar.is_suspended or bar.is_delisted or bar.data_quality in {"partial", "unavailable"} for bar in bars):
        return "partial"
    if latest_bar_date and bars[-1].trade_date < latest_bar_date:
        return "partial"
    return "ok"


def aggregate_quality(items: list[StrategyTrackingItemOut]) -> str:
    if not items:
        return "unavailable"
    qualities = {item.data_quality for item in items}
    if "unavailable" in qualities or "partial" in qualities:
        return "partial"
    return "ok"


def data_quality_text(data_quality: str) -> str:
    return {
        "ok": "数据完整",
        "partial": "部分行情或 payload 缺失，已降级展示",
        "unavailable": "后续行情数据不足，暂时不能判断推荐后的表现",
    }.get(data_quality, "数据状态未知")


def missing_signal_days(rows: tuple[LowBuyResultSnapshot, ...], latest_known_date: str) -> int:
    if not rows or not latest_known_date:
        return 0
    last_signal_date = max(str(row.latest_trade_date) for row in rows)
    return max(0, _date_to_ordinal(latest_known_date) - _date_to_ordinal(last_signal_date))


def conclusion(lifecycle_status: str, stats: dict[str, Any], entry_distance: float | None) -> str:
    if lifecycle_status == "stopped":
        return "已跌破止损"
    if lifecycle_status == "completed_profit":
        return "已达到止盈观察"
    if stats["entry_touched"] and entry_distance == 0:
        return "仍在买点区"
    if entry_distance is not None and entry_distance > 0:
        return "已高于买点，不追高"
    if lifecycle_status == "data_unavailable":
        return "后续行情不足"
    return "等待确认"


def failure_reason(lifecycle_status: str, stats: dict[str, Any]) -> str:
    if lifecycle_status == "stopped" and not stats["entry_touched"]:
        return "推荐后未触达买点直接下跌"
    if lifecycle_status == "stopped":
        return "跌破止损"
    if stats["max_drawdown_pct"] is not None and stats["max_drawdown_pct"] <= -8:
        return "推荐后回撤扩大"
    return ""


def review_text(payload: dict[str, Any], lifecycle_status: str, stats: dict[str, Any]) -> str:
    reason = text(payload, "summary_reason", "execution_note") or "生产策略推荐跟踪"
    if lifecycle_status == "completed_profit":
        return f"{reason}；推荐后出现冲高，进入止盈观察。"
    if lifecycle_status == "stopped":
        return f"{reason}；推荐后跌破止损，需复盘失败原因。"
    if not stats["entry_touched"]:
        return f"{reason}；尚未明确给到买点。"
    return f"{reason}；买点触达后继续观察强弱。"


def build_summary(items: list[StrategyTrackingItemOut]) -> StrategyTrackingSummaryOut:
    returns = [item.current_return_pct for item in items if item.current_return_pct is not None]
    gains = [item.max_gain_pct for item in items if item.max_gain_pct is not None]
    today = max((item.latest_signal_date for item in items), default="")
    quality = aggregate_quality(items)
    return StrategyTrackingSummaryOut(
        tracking_count=len(items),
        active_count=sum(1 for item in items if item.lifecycle_status == "active"),
        today_new_count=sum(1 for item in items if item.first_signal_date == today),
        in_entry_zone_count=sum(1 for item in items if item.entry_touched and item.lifecycle_status == "active"),
        stopped_count=sum(1 for item in items if item.stop_triggered),
        avg_current_return_pct=round_value(sum(returns) / len(returns)) if returns else 0.0,
        median_max_gain_pct=round_value(float(median(gains))) if gains else 0.0,
        data_quality=quality,
        data_quality_text=data_quality_text(quality),
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


def build_performance(items: list[StrategyTrackingItemOut]) -> list[StrategyTrackingPerformanceOut]:
    grouped: dict[str, list[StrategyTrackingItemOut]] = {}
    for item in items:
        grouped.setdefault(item.strategy_key, []).append(item)
    rows = []
    for strategy_key, strategy_items in grouped.items():
        returns = [item.current_return_pct or 0.0 for item in strategy_items]
        gains = [item.max_gain_pct or 0.0 for item in strategy_items]
        drawdowns = [item.max_drawdown_pct or 0.0 for item in strategy_items]
        wins = [value for value in returns if value > 0]
        losses = [abs(value) for value in returns if value < 0]
        rows.append(
            StrategyTrackingPerformanceOut(
                strategy_key=strategy_key,
                strategy_name=strategy_items[0].strategy_name,
                strategy_family=strategy_items[0].strategy_family,
                recommendation_count=len(strategy_items),
                entry_touched_count=sum(1 for item in strategy_items if item.entry_touched),
                entry_touch_rate=ratio(sum(1 for item in strategy_items if item.entry_touched), len(strategy_items)),
                win_rate_3d=win_rate(strategy_items, 3),
                win_rate_5d=win_rate(strategy_items, 5),
                win_rate_10d=win_rate(strategy_items, 10),
                avg_current_return_pct=avg(returns),
                avg_max_gain_pct=avg(gains),
                avg_max_drawdown_pct=avg(drawdowns),
                profit_loss_ratio=round_value((sum(wins) / len(wins)) / (sum(losses) / len(losses))) if wins and losses else 0.0,
                stop_loss_rate=ratio(sum(1 for item in strategy_items if item.stop_triggered), len(strategy_items)),
                active_count=sum(1 for item in strategy_items if item.lifecycle_status == "active"),
            )
        )
    return sorted(rows, key=lambda item: (item.avg_max_gain_pct, item.recommendation_count), reverse=True)


def _date_to_ordinal(value: str) -> int:
    try:
        from datetime import date

        return date.fromisoformat(value).toordinal()
    except ValueError:
        return 0
