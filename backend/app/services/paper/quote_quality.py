from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PaperQuotePrice:
    symbol: str
    price: float
    quality: str
    source: str = ""
    message: str = ""

    @property
    def usable(self) -> bool:
        return self.price > 0 and self.quality in {"fresh", "estimated"}
