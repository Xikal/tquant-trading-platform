from __future__ import annotations

from dataclasses import dataclass

from app.services.indicators import moving_average


@dataclass(frozen=True)
class MaLevels:
    ma5: float | None = None
    ma10: float | None = None
    ma20: float | None = None
    ma30: float | None = None
    ma60: float | None = None


def calculate_ma_levels(closes: list[float]) -> MaLevels:
    if not closes:
        return MaLevels()
    return MaLevels(
        ma5=_ma_or_none(closes, 5),
        ma10=_ma_or_none(closes, 10),
        ma20=_ma_or_none(closes, 20),
        ma30=_ma_or_none(closes, 30),
        ma60=_ma_or_none(closes, 60),
    )


def _ma_or_none(values: list[float], window: int) -> float | None:
    if len(values) < window:
        return None
    return moving_average(values, window)
