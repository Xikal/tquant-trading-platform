from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MarketStateCategory:
    key: str
    label: str
    description: str
    raw_states: tuple[str, ...]


MARKET_STATE_CATEGORIES: dict[str, MarketStateCategory] = {
    "broad_rally": MarketStateCategory(
        key="broad_rally",
        label="强势主升",
        description="个股和行业扩散同步改善，主线强度较高，生产策略可正常参与排序。",
        raw_states=("broad_rally",),
    ),
    "repair": MarketStateCategory(
        key="repair",
        label="弱势修复",
        description="市场从弱势中修复但尚未普涨，优先保留强结构和主线票。",
        raw_states=("repair",),
    ),
    "weight_support": MarketStateCategory(
        key="weight_support",
        label="震荡轮动",
        description="指数可能由权重支撑或热点轮动，题材后排需要降级处理。",
        raw_states=("weight_support", "weight_support_active"),
    ),
    "low_volume_wait": MarketStateCategory(
        key="low_volume_wait",
        label="缩量无主线",
        description="成交和扩散不足，主线不清晰，默认降低新开仓优先级。",
        raw_states=("low_volume_wait",),
    ),
    "fast_rotation": MarketStateCategory(
        key="fast_rotation",
        label="轮动过快",
        description="热点切换速度偏快，只保留辨识度更高的主线结构。",
        raw_states=("fast_rotation",),
    ),
    "risk_retreat": MarketStateCategory(
        key="risk_retreat",
        label="下跌退潮",
        description="高位退潮、风险释放或极端弱势，新增买点需要严格收缩或暂停。",
        raw_states=("high_flyer_retreat", "risk_release"),
    ),
}


_RAW_TO_CATEGORY = {
    raw_state: category.key
    for category in MARKET_STATE_CATEGORIES.values()
    for raw_state in category.raw_states
}


def standard_market_state_key(raw_state: str | None) -> str:
    return _RAW_TO_CATEGORY.get(raw_state or "", "low_volume_wait")


def standard_market_state(raw_state: str | None) -> MarketStateCategory:
    return MARKET_STATE_CATEGORIES[standard_market_state_key(raw_state)]


def standard_market_state_label(raw_state: str | None) -> str:
    return standard_market_state(raw_state).label


def standard_market_state_description(raw_state: str | None) -> str:
    return standard_market_state(raw_state).description


def standard_market_state_payload(raw_state: str | None) -> dict[str, str]:
    category = standard_market_state(raw_state)
    return {
        "market_state_category": category.key,
        "market_state_category_text": category.label,
        "market_state_category_description": category.description,
    }
