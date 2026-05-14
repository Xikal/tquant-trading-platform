from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EmotionTemperature:
    key: str
    text: str
    score: float


def classify_emotion_temperature(
    *,
    limit_up_count: int,
    board_height: int,
    promotion_ratio: float,
    broken_board_ratio: float,
    distribution_pressure: float,
) -> EmotionTemperature:
    score = _score(
        limit_up_count=limit_up_count,
        board_height=board_height,
        promotion_ratio=promotion_ratio,
        broken_board_ratio=broken_board_ratio,
        distribution_pressure=distribution_pressure,
    )
    if score < 30:
        return EmotionTemperature("cold", "冷区：接力弱，低吸信号需要收缩", round(score, 2))
    if score < 58:
        return EmotionTemperature("warm", "温区：可精选主线承接", round(score, 2))
    if score < 78:
        return EmotionTemperature("hot", "热区：情绪活跃，注意冲高兑现", round(score, 2))
    return EmotionTemperature("overheated", "过热区：优先减仓和做T兑现", round(score, 2))


def _score(
    *,
    limit_up_count: int,
    board_height: int,
    promotion_ratio: float,
    broken_board_ratio: float,
    distribution_pressure: float,
) -> float:
    raw = (
        _norm(limit_up_count, 8, 75) * 35
        + _norm(board_height, 1, 6) * 20
        + _norm(promotion_ratio, 0.05, 0.55) * 25
        - _norm(broken_board_ratio, 0.05, 0.45) * 12
        - _norm(distribution_pressure, 0.15, 0.75) * 18
    )
    return max(0.0, min(100.0, raw + 20.0))


def _norm(value: float, low: float, high: float) -> float:
    if high <= low:
        return 0.0
    return max(0.0, min(1.0, (float(value) - low) / (high - low)))
