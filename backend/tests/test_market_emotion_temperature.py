from __future__ import annotations

import pytest

from app.services.market.emotion_temperature import classify_emotion_temperature


def test_classify_emotion_temperature_accepts_documented_ratio_inputs() -> None:
    result = classify_emotion_temperature(
        limit_up_count=45,
        board_height=4,
        promotion_ratio=0.32,
        broken_board_ratio=0.18,
        distribution_pressure=0.28,
    )

    assert result.key in {"cold", "warm", "hot", "overheated"}
    assert result.score >= 0


def test_classify_emotion_temperature_rejects_ambiguous_ratio_inputs() -> None:
    with pytest.raises(ValueError, match="promotion_ratio"):
        classify_emotion_temperature(
            limit_up_count=45,
            board_height=4,
            promotion_ratio=1.2,
            broken_board_ratio=0.18,
            distribution_pressure=0.28,
        )
