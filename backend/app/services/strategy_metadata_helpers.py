from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.entities import StrategyMetadata, StrategyPreset, User
from app.models.schema_defs.strategy_meta import StrategyPresetOut
from app.services.low_buy.strategy_governance import _strategy_health
from app.services.low_buy.strategy_policy import StrategyTier, get_strategy_tier, is_observation_layer_strategy
from app.services.shared.feature_flags import feature_enabled
from app.services.strategy_metadata_defaults import (
    RESEARCH_TO_AUXILIARY_GATED_STRATEGIES,
    RESEARCH_TO_AUXILIARY_MIN_FILLED,
    RESEARCH_TO_AUXILIARY_MIN_HEALTH,
    StrategyDisplaySeed,
)


def promotion_readiness_fields(strategy_key: str, performance) -> dict[str, Any]:
    if strategy_key not in RESEARCH_TO_AUXILIARY_GATED_STRATEGIES:
        return {
            "promotion_eligible": False,
            "promotion_status_text": "",
            "promotion_filled_signals": 0,
            "promotion_health_score": 0.0,
            "promotion_required_filled": 0,
            "promotion_required_health": 0.0,
        }
    health_score, _ = _strategy_health(performance)
    filled = int(getattr(performance, "filled_signals", 0) or 0)
    eligible = filled >= RESEARCH_TO_AUXILIARY_MIN_FILLED and health_score >= RESEARCH_TO_AUXILIARY_MIN_HEALTH
    status = (
        "已满足升入辅助层条件"
        if eligible
        else f"研究层观察中：真实成交 {filled}/{RESEARCH_TO_AUXILIARY_MIN_FILLED}，健康分 {health_score:.1f}/{RESEARCH_TO_AUXILIARY_MIN_HEALTH:.1f}"
    )
    return {
        "promotion_eligible": eligible,
        "promotion_status_text": status,
        "promotion_filled_signals": filled,
        "promotion_health_score": round(float(health_score), 2),
        "promotion_required_filled": RESEARCH_TO_AUXILIARY_MIN_FILLED,
        "promotion_required_health": RESEARCH_TO_AUXILIARY_MIN_HEALTH,
    }


def preset_from_seed(item: dict[str, Any], *, production_keys: list[str]) -> StrategyPresetOut:
    config = dict(item.get("config") or {})
    config["strategies"] = list(production_keys)
    return StrategyPresetOut(
        id=None,
        key=str(item["key"]),
        name=str(item["name"]),
        description=str(item.get("description") or ""),
        config=config,
        sort_order=int(item.get("sort_order") or 0),
    )


def preset_from_row(row: StrategyPreset) -> StrategyPresetOut:
    try:
        config = json.loads(row.config_json or "{}")
    except json.JSONDecodeError:
        config = {}
    return StrategyPresetOut(
        id=row.id,
        key=str(row.preset_key or row.id),
        name=row.name,
        description=row.description or "",
        config=config,
        sort_order=row.sort_order or 0,
    )


def filter_preset(preset: StrategyPresetOut, *, production_keys: list[str]) -> StrategyPresetOut:
    config = dict(preset.config or {})
    configured = config.get("strategies")
    if isinstance(configured, list) and configured:
        allowed = set(production_keys)
        config["strategies"] = [str(item) for item in configured if str(item) in allowed]
    if not config.get("strategies"):
        config["strategies"] = list(production_keys)
    preset.config = config
    return preset


def escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def strategy_tier(seed: StrategyDisplaySeed) -> StrategyTier:
    try:
        return StrategyTier(seed.tier)
    except ValueError:
        return get_strategy_tier(seed.key)


def metadata_fallback_tier(seed: StrategyDisplaySeed | None, row: StrategyMetadata | None) -> StrategyTier:
    if row is not None:
        normalized = normalize_tier(getattr(row, "category", "") or "")
        if normalized in {"core", "auxiliary", "research", "factor"}:
            return StrategyTier(normalized)
    if seed is not None:
        return strategy_tier(seed)
    return StrategyTier.RESEARCH


def strategy_tier_label(tier: StrategyTier) -> str:
    return {
        StrategyTier.CORE: "生产策略",
        StrategyTier.AUXILIARY: "辅助策略",
        StrategyTier.RESEARCH: "研究策略",
        StrategyTier.FACTOR: "辅助因子",
    }.get(tier, "研究策略")


def display_category(value: str | None, tier: StrategyTier, strategy_key: str = "") -> str:
    if strategy_key and is_observation_layer_strategy(strategy_key):
        return "观察策略"
    normalized = (value or "").strip()
    if normalized in {"core", "auxiliary", "research", "factor"}:
        return strategy_tier_label(StrategyTier(normalized))
    return normalized or strategy_tier_label(tier)


def strategy_feature_enabled(db: Session, strategy_key: str, *, default: bool) -> bool:
    if not hasattr(db, "execute"):
        return default
    return feature_enabled(db, f"strategy_{strategy_key}_enabled", default)


def roles(current_user: User | None) -> set[str]:
    if current_user is None:
        return set()
    raw_roles = getattr(current_user, "roles", None)
    parsed_roles: set[str] = set()
    if isinstance(raw_roles, str):
        parsed_roles.update(role.strip().lower() for role in raw_roles.replace(";", ",").split(",") if role.strip())
    elif isinstance(raw_roles, (list, tuple, set)):
        parsed_roles.update(str(role).strip().lower() for role in raw_roles if str(role).strip())
    if getattr(current_user, "is_admin", False) or getattr(current_user, "is_superuser", False):
        parsed_roles.add("admin")
    return parsed_roles


def has_any_role(roles: set[str], expected: set[str]) -> bool:
    return bool(roles.intersection(expected))


def row_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "on", "enabled"}


def row_text(value: Any, default: str) -> str:
    text = str(value or "").strip()
    return text or default


def normalize_tier(value: str) -> str:
    normalized = (value or "").strip().lower()
    return {
        "production": "core",
        "prod": "core",
        "辅助": "auxiliary",
        "研究": "research",
        "因子": "factor",
    }.get(normalized, normalized)
