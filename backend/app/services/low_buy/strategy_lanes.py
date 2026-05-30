from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal


StrategyVariant = Literal["baseline", "front_row_weighted", "front_row_only"]
StrategyRole = Literal["production_baseline", "shadow_paper_candidate", "elite_watch"]
DisplayLane = Literal["baseline", "front_row_weighted", "front_row_only"]

BASELINE_VARIANT: StrategyVariant = "baseline"
FRONT_ROW_WEIGHTED_VARIANT: StrategyVariant = "front_row_weighted"
FRONT_ROW_ONLY_VARIANT: StrategyVariant = "front_row_only"
STRATEGY_VARIANTS: tuple[StrategyVariant, ...] = (
    BASELINE_VARIANT,
    FRONT_ROW_WEIGHTED_VARIANT,
    FRONT_ROW_ONLY_VARIANT,
)
FRONT_ROW_ONLY_TIERS = {"core_leader", "leader_hot", "strong_follower"}


@dataclass(frozen=True)
class StrategyLaneDefinition:
    variant: StrategyVariant
    role: StrategyRole
    display_lane: DisplayLane
    title: str
    subtitle: str
    production_sort_replaced: bool
    production_enabled: bool
    paper_enabled: bool
    watch_only: bool

    def as_payload(self) -> dict[str, object]:
        return asdict(self)


LANES: dict[StrategyVariant, StrategyLaneDefinition] = {
    BASELINE_VARIANT: StrategyLaneDefinition(
        variant=BASELINE_VARIANT,
        role="production_baseline",
        display_lane=BASELINE_VARIANT,
        title="原低吸策略",
        subtitle="当前生产观察基准，保留原来的具体策略名称和旧排序。",
        production_sort_replaced=False,
        production_enabled=True,
        paper_enabled=False,
        watch_only=False,
    ),
    FRONT_ROW_WEIGHTED_VARIANT: StrategyLaneDefinition(
        variant=FRONT_ROW_WEIGHTED_VARIANT,
        role="shadow_paper_candidate",
        display_lane=FRONT_ROW_WEIGHTED_VARIANT,
        title="前排加权",
        subtitle="只做验证，暂不影响真实排序。",
        production_sort_replaced=False,
        production_enabled=False,
        paper_enabled=True,
        watch_only=False,
    ),
    FRONT_ROW_ONLY_VARIANT: StrategyLaneDefinition(
        variant=FRONT_ROW_ONLY_VARIANT,
        role="elite_watch",
        display_lane=FRONT_ROW_ONLY_VARIANT,
        title="前排极精选",
        subtitle="前排极精选只做提醒，不作为生产硬过滤。",
        production_sort_replaced=False,
        production_enabled=False,
        paper_enabled=False,
        watch_only=True,
    ),
}


def normalize_strategy_variant(value: str | None, *, front_row_only: bool = False) -> StrategyVariant:
    if front_row_only:
        return FRONT_ROW_ONLY_VARIANT
    normalized = str(value or BASELINE_VARIANT).strip().lower()
    if normalized in LANES:
        return normalized  # type: ignore[return-value]
    return BASELINE_VARIANT


def resolve_strategy_lane(value: str | None, *, front_row_only: bool = False) -> StrategyLaneDefinition:
    return LANES[normalize_strategy_variant(value, front_row_only=front_row_only)]


def available_lane_payloads() -> list[dict[str, object]]:
    return [LANES[key].as_payload() for key in STRATEGY_VARIANTS]


def lane_payload(value: str | None) -> dict[str, object]:
    return resolve_strategy_lane(value).as_payload()


def matched_strategy_variants_for_item(item: Any, *, current_variant: str | None = None) -> list[str]:
    variants: list[str] = []
    normalized = normalize_strategy_variant(current_variant)
    if normalized == BASELINE_VARIANT:
        variants.append(BASELINE_VARIANT)
    if getattr(item, "production_score", None) is not None:
        variants.append(FRONT_ROW_WEIGHTED_VARIANT)
    if _front_row_only_candidate(item):
        variants.append(FRONT_ROW_ONLY_VARIANT)
    if normalized not in variants:
        variants.insert(0, normalized)
    return _dedupe(variants)


def item_matches_strategy_variant(item: Any, strategy_variant: str | None) -> bool:
    variant = normalize_strategy_variant(strategy_variant)
    if variant == BASELINE_VARIANT:
        return True
    if variant == FRONT_ROW_WEIGHTED_VARIANT:
        return getattr(item, "production_score", None) is not None
    return _front_row_only_candidate(item)


def lane_item_update(item: Any, strategy_variant: str | None) -> dict[str, object]:
    lane = resolve_strategy_lane(strategy_variant)
    matched = matched_strategy_variants_for_item(item, current_variant=lane.variant)
    update: dict[str, object] = {
        "strategy_variant": lane.variant,
        "strategy_role": lane.role,
        "display_lane": lane.display_lane,
        "display_lane_title": lane.title,
        "display_lane_subtitle": lane.subtitle,
        "production_sort_replaced": lane.production_sort_replaced,
        "production_enabled": lane.production_enabled,
        "paper_enabled": lane.paper_enabled,
        "watch_only": lane.watch_only,
        "matched_strategy_variants": matched,
        "primary_lane_reason": primary_lane_reason(lane.variant, matched),
    }
    if lane.variant == FRONT_ROW_ONLY_VARIANT:
        watch_score = getattr(item, "watch_score", None)
        priority_score = getattr(item, "priority_score", None)
        update.update(
            {
                "production_score": None,
                "elite_watch_score": watch_score if watch_score is not None else priority_score,
                "production_enabled": False,
                "paper_enabled": False,
                "watch_only": True,
            }
        )
    return update


def project_item_to_lane(item: Any, strategy_variant: str | None) -> Any:
    update = lane_item_update(item, strategy_variant)
    copier = getattr(item, "model_copy", None)
    if callable(copier):
        return copier(update=update)
    for key, value in update.items():
        setattr(item, key, value)
    return item


def project_items_to_lane(items: list[Any], strategy_variant: str | None) -> list[Any]:
    return [project_item_to_lane(item, strategy_variant) for item in items if item_matches_strategy_variant(item, strategy_variant)]


def primary_lane_reason(strategy_variant: str | None, matched_variants: list[str] | None = None) -> str:
    variant = normalize_strategy_variant(strategy_variant)
    if variant == FRONT_ROW_WEIGHTED_VARIANT:
        return "前排加权验证池，只做验证，暂不影响真实排序。"
    if variant == FRONT_ROW_ONLY_VARIANT:
        return "前排极精选只做提醒，不作为生产硬过滤。"
    if matched_variants and len(matched_variants) > 1:
        return "原低吸策略大分组，具体策略名称保留；该票也命中其他观察线。"
    return "原低吸策略大分组，保留原来的具体策略名称和旧排序。"


def lane_summary(strategy_variant: str | None, items: list[Any]) -> dict[str, object]:
    lane = resolve_strategy_lane(strategy_variant)
    matched_count = sum(1 for item in items if len(getattr(item, "matched_strategy_variants", []) or []) > 1)
    return {
        **lane.as_payload(),
        "item_count": len(items),
        "matched_multi_lane_count": matched_count,
        "plain_status": plain_status_for_lane(lane.variant),
    }


def plain_status_for_lane(strategy_variant: str | None) -> dict[str, str]:
    variant = normalize_strategy_variant(strategy_variant)
    if variant == FRONT_ROW_WEIGHTED_VARIANT:
        return {
            "conclusion": "只做验证，暂不影响真实排序",
            "reason": "样本外验证不足、滚动验证不稳定、成交数据不足",
            "next_step": "继续影子验证和模拟盘观察",
        }
    if variant == FRONT_ROW_ONLY_VARIANT:
        return {
            "conclusion": "只做提醒，不参与生产排序",
            "reason": "信号很少，可能连续多天没有票",
            "next_step": "继续作为强前排观察池",
        }
    return {
        "conclusion": "保持旧策略排序",
        "reason": "原低吸策略是大分组，里面仍保留各自具体策略名称",
        "next_step": "继续作为当前生产观察基准",
    }


def _front_row_only_candidate(item: Any) -> bool:
    tier = str(getattr(item, "front_row_tier", "") or "").strip()
    if tier in FRONT_ROW_ONLY_TIERS:
        return True
    leader_rank = str(getattr(item, "leader_rank", "") or "")
    leader_rank_value = int(getattr(item, "leader_strength_rank", 0) or 0)
    leader_score = float(getattr(item, "leader_strength_score", 0.0) or 0.0)
    return leader_rank in {"leader", "strong_follow"} and 0 < leader_rank_value <= 3 and leader_score >= 58.0


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result
