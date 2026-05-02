from __future__ import annotations

from dataclasses import dataclass

INDUSTRY_TIER_LABELS = {
    "core_hot": "核心热点",
    "secondary_hot": "次级热点",
    "neutral": "中性行业",
    "cold": "弱势行业",
}

_BASE_INDUSTRY_MULTIPLIERS = {
    "core_hot": 1.08,
    "secondary_hot": 1.0,
    "neutral": 0.92,
    "cold": 0.82,
}

_DEFENSIVE_STATES = {
    "weight_support",
    "low_volume_wait",
    "fast_rotation",
    "high_flyer_retreat",
    "risk_release",
}


@dataclass(frozen=True)
class IndustryPositionAdjustment:
    tier: str
    label: str
    multiplier: float
    note: str


def resolve_industry_tier(
    *,
    sector_name: str | None,
    hot_industries: list[str],
    leader_rank: str,
) -> str:
    sector = (sector_name or "").strip()
    if not sector or not hot_industries:
        return "neutral" if leader_rank != "laggard" else "cold"
    if sector == hot_industries[0] and leader_rank in {"leader", "strong_follow"}:
        return "core_hot"
    if sector in hot_industries:
        return "secondary_hot"
    if leader_rank == "laggard":
        return "cold"
    return "neutral"


def build_industry_position_adjustment(
    *,
    sector_name: str | None,
    hot_industries: list[str],
    leader_rank: str,
    market_state: str,
    market_state_strength: float,
) -> IndustryPositionAdjustment:
    tier = resolve_industry_tier(
        sector_name=sector_name,
        hot_industries=hot_industries,
        leader_rank=leader_rank,
    )
    multiplier = _BASE_INDUSTRY_MULTIPLIERS.get(tier, 0.92)
    multiplier = _apply_market_guard(
        tier=tier,
        multiplier=multiplier,
        market_state=market_state,
        market_state_strength=market_state_strength,
    )
    label = INDUSTRY_TIER_LABELS.get(tier, "中性行业")
    return IndustryPositionAdjustment(
        tier=tier,
        label=label,
        multiplier=round(multiplier, 4),
        note=_industry_note(label, sector_name),
    )


def industry_tier_label(tier: str) -> str:
    return INDUSTRY_TIER_LABELS.get(tier, "中性行业")


def _apply_market_guard(
    *,
    tier: str,
    multiplier: float,
    market_state: str,
    market_state_strength: float,
) -> float:
    strength = max(0.0, min(market_state_strength, 1.0))
    if market_state == "risk_release":
        return min(multiplier, 0.72)
    if market_state == "high_flyer_retreat":
        cap = 0.95 if tier == "core_hot" else 0.82
        return min(multiplier, cap - strength * 0.08)
    if market_state in _DEFENSIVE_STATES and tier not in {"core_hot", "secondary_hot"}:
        return min(multiplier, 0.88 - strength * 0.06)
    if market_state == "broad_rally" and tier == "core_hot":
        return min(multiplier + 0.03, 1.12)
    return multiplier


def _industry_note(label: str, sector_name: str | None) -> str:
    sector = (sector_name or "").strip() or "未分类行业"
    return f"{sector} 属于{label}"
