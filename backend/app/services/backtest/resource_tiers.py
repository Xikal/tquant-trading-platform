from __future__ import annotations

import json
from typing import Any, Literal

BacktestResourceTier = Literal["light", "full", "walk_forward"]

DEFAULT_BACKTEST_RESOURCE_TIER: BacktestResourceTier = "full"
RESOURCE_TIER_SECONDS: dict[BacktestResourceTier, int] = {
    "light": 30,
    "full": 60,
    "walk_forward": 180,
}


def normalize_backtest_resource_tier(value: Any) -> BacktestResourceTier:
    cleaned = str(value or "").strip().lower()
    if cleaned in RESOURCE_TIER_SECONDS:
        return cleaned  # type: ignore[return-value]
    return DEFAULT_BACKTEST_RESOURCE_TIER


def resource_tier_from_params(params: dict[str, Any] | None) -> BacktestResourceTier:
    return normalize_backtest_resource_tier((params or {}).get("resource_tier"))


def resource_tier_from_params_json(raw: str | None) -> BacktestResourceTier:
    try:
        payload = json.loads(raw or "{}")
    except Exception:
        return DEFAULT_BACKTEST_RESOURCE_TIER
    if not isinstance(payload, dict):
        return DEFAULT_BACKTEST_RESOURCE_TIER
    return resource_tier_from_params(payload)


def estimated_seconds_for_tier(tier: BacktestResourceTier) -> int:
    return int(RESOURCE_TIER_SECONDS.get(tier, RESOURCE_TIER_SECONDS[DEFAULT_BACKTEST_RESOURCE_TIER]))
