from __future__ import annotations

from collections import defaultdict

from app.models.schema_defs.key_levels import KeyLevelCandidate
from app.repositories.low_buy.daily_history import DailyBarRow
from app.services.key_levels.score import clamp_score, zone_for_price


def build_volume_profile_candidates(rows: list[DailyBarRow], latest_price: float) -> list[KeyLevelCandidate]:
    if len(rows) < 20 or latest_price <= 0:
        return []
    window = rows[-120:] if len(rows) >= 120 else rows
    buckets: dict[float, float] = defaultdict(float)
    for row in window:
        low_price = float(row.low_price or 0)
        high_price = float(row.high_price or 0)
        amount = float(row.amount or 0)
        if low_price <= 0 or high_price <= 0 or amount <= 0:
            continue
        midpoint = (low_price + high_price) / 2
        bucket = round(midpoint / max(midpoint * 0.01, 0.1)) * max(midpoint * 0.01, 0.1)
        buckets[round(bucket, 2)] += amount
    ranked = sorted(buckets.items(), key=lambda item: item[1], reverse=True)
    candidates: list[KeyLevelCandidate] = []
    support = next((price for price, _amount in ranked if price <= latest_price), None)
    resistance = next((price for price, _amount in ranked if price >= latest_price), None)
    if support:
        candidates.append(_candidate(price=support, direction="support", source_window_days=len(window)))
    if resistance and resistance != support:
        candidates.append(_candidate(price=resistance, direction="resistance", source_window_days=len(window)))
    return candidates


def _candidate(*, price: float, direction: str, source_window_days: int) -> KeyLevelCandidate:
    zone_low, zone_high = zone_for_price(price, 0.005)
    return KeyLevelCandidate(
        price=round(price, 4),
        zone_low=zone_low,
        zone_high=zone_high,
        direction=direction,  # type: ignore[arg-type]
        level_type="volume_profile",
        strength_score=clamp_score(62),
        evidence=["近 120 个交易日成交密集区", "成交额分桶估算"],
        invalid_condition=(
            f"放量跌破 {zone_low:.2f} 且未收回，支撑降级"
            if direction == "support"
            else f"接近 {zone_high:.2f} 压力区，观察承接和站稳情况"
        ),
        source_window_days=source_window_days,
        invalidate_below=zone_low if direction == "support" else None,
        invalidate_volume_x=1.5,
    )
