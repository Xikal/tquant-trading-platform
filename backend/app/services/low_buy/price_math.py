from __future__ import annotations

from app.models.schemas import LowBuyCandidateOut


def distance_to_entry_zone_pct(candidate: LowBuyCandidateOut, latest_price: float) -> float:
    if candidate.entry_zone_low <= latest_price <= candidate.entry_zone_high:
        return 0.0
    if latest_price > candidate.entry_zone_high:
        return round(((latest_price - candidate.entry_zone_high) / max(candidate.entry_zone_high, 0.01)) * 100, 3)
    return round(((candidate.entry_zone_low - latest_price) / max(candidate.entry_zone_low, 0.01)) * 100, 3)
