from __future__ import annotations

from app.models.schema_defs.key_levels import KeyLevelCandidate
from app.repositories.low_buy.daily_history import DailyBarRow
from app.services.key_levels.score import clamp_score, zone_for_price


def build_anchored_vwap_candidates(rows: list[DailyBarRow], latest_price: float) -> list[KeyLevelCandidate]:
    if len(rows) < 20 or latest_price <= 0:
        return []
    anchor_index = _find_anchor_index(rows)
    if anchor_index is None:
        return []
    anchor_rows = rows[anchor_index:]
    amount_sum = sum(float(row.amount or 0) for row in anchor_rows)
    volume_sum = sum(float(row.volume or 0) for row in anchor_rows)
    if amount_sum <= 0 or volume_sum <= 0:
        return []
    price = amount_sum / volume_sum
    if price <= 0:
        return []
    direction = "support" if price <= latest_price else "resistance"
    zone_low, zone_high = zone_for_price(price, 0.004)
    return [
        KeyLevelCandidate(
            price=round(price, 4),
            zone_low=zone_low,
            zone_high=zone_high,
            direction=direction,  # type: ignore[arg-type]
            level_type="anchored_vwap",
            strength_score=clamp_score(55),
            evidence=["放量日 Anchored VWAP", "事件后平均成本近似"],
            invalid_condition=(
                f"跌破 {zone_low:.2f} 且未收回，锚定均价支撑降级"
                if direction == "support"
                else f"接近 {zone_high:.2f} 锚定均价压力，观察能否站稳"
            ),
            last_touched_date=str(anchor_rows[0].trade_date),
            source_window_days=len(anchor_rows),
            invalidate_below=zone_low if direction == "support" else None,
            invalidate_volume_x=1.5,
        )
    ]


def _find_anchor_index(rows: list[DailyBarRow]) -> int | None:
    if len(rows) < 20:
        return None
    avg_amount = sum(float(row.amount or 0) for row in rows[-60:]) / max(1, len(rows[-60:]))
    best_index = None
    best_amount = 0.0
    for index, row in enumerate(rows[-60:], start=max(0, len(rows) - 60)):
        amount = float(row.amount or 0)
        high_price = float(row.high_price or 0)
        low_price = float(row.low_price or 0)
        close_price = float(row.close_price or 0)
        open_price = float(row.open_price or 0)
        if amount < avg_amount * 1.2:
            continue
        if high_price <= low_price or close_price <= open_price:
            continue
        if amount > best_amount:
            best_index = index
            best_amount = amount
    return best_index
