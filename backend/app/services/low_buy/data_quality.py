from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DataQualitySnapshot:
    quality: str = "ok"
    text: str = "数据完整"
    tags: tuple[str, ...] = ()


_SEVERITY = {
    "ok": 0,
    "partial": 1,
    "stale": 2,
    "degraded": 2,
    "limited": 3,
    "unavailable": 4,
}


def build_market_data_quality(
    *,
    breadth_ready: bool,
    emotion_ready: bool,
    hot_industry_source: str = "",
    snapshot_warning: str = "",
) -> DataQualitySnapshot:
    tags: list[str] = []
    if snapshot_warning:
        tags.append("快照回退")
    if hot_industry_source in {"cached_fallback", "unavailable", "fallback", "none"}:
        tags.append("热点数据回退")
    if not breadth_ready:
        tags.append("市场广度缺失")
    if not emotion_ready:
        tags.append("情绪数据缺失")

    if breadth_ready and emotion_ready and not tags:
        return DataQualitySnapshot()
    if breadth_ready or emotion_ready:
        return DataQualitySnapshot("partial", "部分市场数据缺失", tuple(tags))
    return DataQualitySnapshot("limited", "市场/情绪数据待补齐", tuple(tags))


def build_candidate_data_quality(
    *,
    latest_price: float,
    quote_timestamp: str = "",
    source_quality: str | None = None,
    is_stale: bool = False,
    change_pct: float | None = None,
    market_quality: DataQualitySnapshot | None = None,
) -> DataQualitySnapshot:
    tags: list[str] = list(market_quality.tags if market_quality is not None else ())
    if latest_price <= 0:
        tags.append("价格无效")
        return DataQualitySnapshot("unavailable", "行情价格不可用", tuple(tags))
    if latest_price > 100000:
        tags.append("价格异常")
        return DataQualitySnapshot("degraded", "行情价格疑似异常", tuple(tags))
    if change_pct is not None and abs(change_pct) > 25:
        tags.append("涨跌幅异常")
        return DataQualitySnapshot("degraded", "行情涨跌幅疑似异常", tuple(tags))
    if not quote_timestamp:
        tags.append("行情时间缺失")
    if is_stale or (source_quality and "stale" in source_quality.lower()):
        tags.append("行情可能延迟")
        return combine_data_quality(
            market_quality or DataQualitySnapshot(),
            DataQualitySnapshot("stale", "行情可能延迟", tuple(tags)),
        )
    if market_quality is not None:
        return market_quality
    if tags:
        return DataQualitySnapshot("partial", "行情字段不完整", tuple(tags))
    return DataQualitySnapshot()


def combine_data_quality(*items: DataQualitySnapshot | None) -> DataQualitySnapshot:
    snapshots = [item for item in items if item is not None]
    if not snapshots:
        return DataQualitySnapshot()
    worst = max(snapshots, key=lambda item: _SEVERITY.get(item.quality, 99))
    tags: list[str] = []
    for item in snapshots:
        tags.extend(tag for tag in item.tags if tag not in tags)
    if not tags:
        return worst
    return DataQualitySnapshot(worst.quality, worst.text, tuple(tags))


def data_quality_payload(snapshot: DataQualitySnapshot) -> dict[str, object]:
    return {
        "data_quality": snapshot.quality,
        "data_quality_text": snapshot.text,
        "data_quality_tags": list(snapshot.tags),
    }
