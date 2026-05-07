from __future__ import annotations

from typing import Any

_FALLBACK_HOT_SOURCES = {"cached_fallback", "unavailable", "fallback", "none"}


def market_regime_quality_text(regime: Any) -> str:
    breadth_ready = bool(getattr(regime, "breadth_ready", False))
    emotion_ready = bool(getattr(regime, "emotion_ready", False))
    hot_industry_source = str(getattr(regime, "hot_industry_source", "") or "")
    snapshot_source = str(getattr(regime, "snapshot_source", "live") or "live")
    if breadth_ready and emotion_ready and hot_industry_source not in _FALLBACK_HOT_SOURCES:
        if snapshot_source == "cached":
            return "使用最近完整市场快照"
        return "实时市场数据"

    missing: list[str] = []
    if not breadth_ready:
        missing.append("市场广度补齐中")
    if not emotion_ready:
        missing.append("涨停/炸板情绪补齐中")
    if hot_industry_source in _FALLBACK_HOT_SOURCES:
        missing.append("热点板块使用回退数据")
    if not missing:
        missing.append("市场数据补齐中")
    if snapshot_source == "cached":
        return f"{'，'.join(missing)}；已使用最近完整快照"
    if snapshot_source == "warming":
        return f"{'，'.join(missing)}；后台刷新中"
    return "，".join(missing)


def market_regime_quality_tags(regime: Any) -> list[str]:
    tags: list[str] = []
    snapshot_source = str(getattr(regime, "snapshot_source", "live") or "live")
    if snapshot_source == "cached":
        tags.append("最近快照")
    if snapshot_source == "warming":
        tags.append("后台刷新")
    if not bool(getattr(regime, "breadth_ready", False)):
        tags.append("市场广度待补齐")
    if not bool(getattr(regime, "emotion_ready", False)):
        tags.append("涨停情绪待补齐")
    if str(getattr(regime, "hot_industry_source", "") or "") in _FALLBACK_HOT_SOURCES:
        tags.append("热点数据回退")
    return tags
