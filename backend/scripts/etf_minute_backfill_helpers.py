from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.models.schemas import KlineBar
from app.services.etf.universe import EtfProfile


MinuteFetcher = Callable[..., list[KlineBar]]


@dataclass(frozen=True)
class ProviderCandidate:
    source: str
    bars: list[KlineBar]

    @property
    def trade_days(self) -> int:
        return len({bar.timestamp[:10] for bar in self.bars if len(bar.timestamp) >= 10})


def select_best_candidate(candidates: list[ProviderCandidate]) -> ProviderCandidate | None:
    if not candidates:
        return None
    return max(candidates, key=lambda item: (item.trade_days, len(item.bars)))


def enrich_etf_bars(profile: EtfProfile, bars: list[KlineBar]) -> list[KlineBar]:
    for bar in bars:
        bar.tracking_index_symbol = profile.tracking_index
        bar.liquidity_tier = liquidity_tier(profile=profile, bar=bar)
        if bar.bid_ask_spread is None:
            bar.bid_ask_spread = 0.0
    return bars


def liquidity_tier(*, profile: EtfProfile, bar: KlineBar) -> str:
    amount = float(bar.amount or 0.0)
    if amount >= float(profile.min_amount or 0.0):
        return "sufficient"
    if amount > 0:
        return "thin"
    return "unknown"


def minute_data_quality(*, profile: EtfProfile, bar: KlineBar) -> str:
    if bar.close <= 0:
        return "unavailable"
    if profile.premium_discount_available and bar.premium_discount_pct is None:
        return "partial_metadata"
    if float(bar.bid_ask_spread or 0.0) <= 0:
        return "partial_metadata"
    return "fresh"


def execution_quality_summary(profile: EtfProfile, bars: list[KlineBar]) -> str:
    counts: dict[str, int] = {}
    for bar in enrich_etf_bars(profile, bars):
        key = minute_data_quality(profile=profile, bar=bar)
        counts[key] = counts.get(key, 0) + 1
    return ",".join(f"{key}:{counts[key]}" for key in sorted(counts))
