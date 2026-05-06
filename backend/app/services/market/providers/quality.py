from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Generic, TypeVar


T = TypeVar("T")


class MarketDataQuality(str, Enum):
    FRESH = "fresh"
    STALE = "stale"
    ESTIMATED = "estimated"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class ProviderResult(Generic[T]):
    quality: MarketDataQuality
    source: str
    data: T | None = None
    message: str = ""
    latency_ms: int = 0

    @property
    def usable(self) -> bool:
        return self.quality in {
            MarketDataQuality.FRESH,
            MarketDataQuality.STALE,
            MarketDataQuality.ESTIMATED,
        } and self.data is not None
