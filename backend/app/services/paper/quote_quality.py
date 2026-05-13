from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PaperQuotePrice:
    symbol: str
    price: float
    quality: str
    source: str = ""
    message: str = ""
    open_price: float = 0.0
    high_price: float = 0.0
    low_price: float = 0.0
    prev_close: float = 0.0
    change_pct: float = 0.0
    volume_ratio: float = 0.0

    @property
    def usable(self) -> bool:
        return self.price > 0 and self.quality in {"fresh", "estimated"}
