from __future__ import annotations

from types import SimpleNamespace

from app.services.low_buy.strategy_validation_phase import resolve_strategy_validation_phase


def _performance(*, filled: int, hits: int, avg_net: float) -> SimpleNamespace:
    return SimpleNamespace(
        filled_signals=filled,
        hit_count=hits,
        hit_rate=round(hits / max(filled, 1) * 100, 2),
        avg_net_return_pct=avg_net,
    )


def test_phase2_requires_statistical_edge_not_only_52_percent_win_rate() -> None:
    phase = resolve_strategy_validation_phase(
        _performance(filled=50, hits=26, avg_net=0.5),
        health_score=70,
    )

    assert phase.phase == "phase2_small"
    assert "二项检验" in phase.reason


def test_phase3_requires_enough_samples_positive_return_and_significance() -> None:
    phase = resolve_strategy_validation_phase(
        _performance(filled=80, hits=50, avg_net=0.5),
        health_score=70,
    )

    assert phase.phase == "phase3_full"
    assert phase.position_scale == 1.0


def test_phase2_keeps_small_position_when_avg_return_is_too_low() -> None:
    phase = resolve_strategy_validation_phase(
        _performance(filled=80, hits=50, avg_net=0.1),
        health_score=70,
    )

    assert phase.phase == "phase2_small"
    assert "均净收益" in phase.reason
