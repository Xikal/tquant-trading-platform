from __future__ import annotations

from typing import Any

from app.services.low_buy.execution_simulation import DailyExecutionBar
from app.services.low_buy.shared import (
    LOW_BUY_PERFORMANCE_SNAPSHOT_VERSION,
    LowBuyPerformanceBucketOut,
    LowBuyStrategyPerformanceOut,
    datetime,
)


def daily_bar_index(rows: list[DailyExecutionBar], trade_date: str) -> int | None:
    for index, row in enumerate(rows):
        if row.trade_date == trade_date:
            return index
    return None


def filled_close_return(
    rows: list[DailyExecutionBar],
    entry_trade_date: str | None,
    entry_price: float,
    holding_days: int,
) -> float:
    if not entry_trade_date or entry_price <= 0:
        return 0.0
    entry_index = daily_bar_index(rows, entry_trade_date)
    if entry_index is None:
        return 0.0
    target_index = min(entry_index + max(holding_days, 1) - 1, len(rows) - 1)
    return (rows[target_index].close_price / entry_price - 1) * 100


def empty_strategy_performance(
    *,
    target_profit_pct: float,
    lookback_days: int = 0,
    note: str | None = None,
) -> LowBuyStrategyPerformanceOut:
    notes = [
        "主命中率按真实执行净收益胜率统计。",
        "净胜优势按盈利笔数减亏损笔数后的成交占比统计。",
        f"5 日内最高价触及 {target_profit_pct:.1f}% 目标仅作为辅助冲高参考。",
    ]
    if note:
        notes.append(note)
    return LowBuyStrategyPerformanceOut(
        snapshot_version=LOW_BUY_PERFORMANCE_SNAPSHOT_VERSION,
        lookback_days=lookback_days,
        target_profit_pct=round(target_profit_pct, 2),
        updated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        data_insufficient=True,
        attribution_notes=notes,
    )


def build_performance_buckets(
    records: list[dict[str, Any]],
    key: str,
    limit: int | None = 3,
    sort_return_field: str = "avg_return_3d",
) -> list[LowBuyPerformanceBucketOut]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in records:
        label = str(item.get(key) or "未分类")
        grouped.setdefault(label, []).append(item)
    buckets: list[LowBuyPerformanceBucketOut] = []
    for label, items in grouped.items():
        sample_count = len(items)
        hit_count = sum(1 for item in items if item["hit"])
        buckets.append(
            LowBuyPerformanceBucketOut(
                label=label,
                sample_count=sample_count,
                hit_count=hit_count,
                hit_rate=round(hit_count / sample_count * 100, 2),
                avg_return_3d=round(sum(item["return_3d"] for item in items) / sample_count, 2),
                avg_return_5d=round(sum(item["return_5d"] for item in items) / sample_count, 2),
            )
        )
    buckets.sort(
        key=lambda item: (
            item.avg_return_5d if sort_return_field == "avg_return_5d" else item.avg_return_3d,
            item.hit_rate,
            item.sample_count,
        ),
        reverse=True,
    )
    if limit is None:
        return buckets
    return buckets[:limit]


def retracement_bucket(retracement_days: int) -> str:
    if retracement_days <= 2:
        return "1-2天回调"
    if retracement_days <= 4:
        return "3-4天回调"
    return "5-7天回调"
