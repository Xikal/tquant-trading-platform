from __future__ import annotations

import time

from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.models.entities import StrategyTierOverride
from app.services.low_buy.strategy_policy import StrategyTier, get_strategy_tier

_CACHE_TTL_SECONDS = 300.0
_CACHE: dict[str, tuple[float, StrategyTier]] = {}


class StrategyTierResolver:
    """Resolve strategy tier with DB overrides without touching hot pure rules."""

    def __init__(self, db: Session | None = None) -> None:
        self.db = db

    def resolve(self, strategy_key: str, fallback: StrategyTier | None = None) -> StrategyTier:
        fallback_tier = fallback or get_strategy_tier(strategy_key)
        if self.db is None:
            return fallback_tier
        cached = _CACHE.get(strategy_key)
        now = time.monotonic()
        if cached and cached[0] > now:
            return cached[1]
        tier = self._load_override(strategy_key) or fallback_tier
        _CACHE[strategy_key] = (now + _CACHE_TTL_SECONDS, tier)
        return tier

    def _load_override(self, strategy_key: str) -> StrategyTier | None:
        try:
            row = self.db.execute(
                select(StrategyTierOverride).where(
                    StrategyTierOverride.strategy_key == strategy_key,
                    StrategyTierOverride.reverted_at.is_(None),
                )
            ).scalar_one_or_none()
        except OperationalError as exc:
            if "no such table" in str(exc).lower():
                return None
            raise
        if row is None:
            return None
        try:
            return StrategyTier(str(row.override_tier or ""))
        except ValueError:
            return None


def clear_strategy_tier_cache(strategy_key: str | None = None) -> None:
    if strategy_key:
        _CACHE.pop(strategy_key, None)
        return
    _CACHE.clear()
