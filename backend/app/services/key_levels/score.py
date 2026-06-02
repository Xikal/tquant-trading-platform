from __future__ import annotations


def clamp_score(value: float) -> int:
    return max(0, min(100, int(round(value))))


def distance_pct(latest_price: float, level_price: float) -> float | None:
    if latest_price <= 0 or level_price <= 0:
        return None
    return round((level_price - latest_price) / latest_price * 100, 4)


def zone_for_price(price: float, pct: float = 0.003) -> tuple[float, float]:
    spread = max(price * pct, 0.01)
    return round(price - spread, 4), round(price + spread, 4)
