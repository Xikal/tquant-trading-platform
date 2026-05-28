from __future__ import annotations

from types import SimpleNamespace

from app.services.low_buy import main_force_model_ranking as ranking
from app.services.low_buy.main_force_model_ranking import main_force_rank_bonus
from backend.tests.main_force_model_test_helpers import main_force_candidate


def test_main_force_ranking_default_is_no_bonus() -> None:
    candidate = main_force_candidate(main_force_advice=_advice())

    assert main_force_rank_bonus(candidate, shadow_status={"promotion_ready": True}) == 0.0


def test_main_force_ranking_enabled_but_shadow_not_ready_is_no_bonus(monkeypatch) -> None:
    monkeypatch.setattr(ranking, "get_settings", lambda: _settings(ranking_enabled=True))
    candidate = main_force_candidate(main_force_advice=_advice())

    assert main_force_rank_bonus(candidate, shadow_status={"promotion_ready": False}) == 0.0


def test_main_force_ranking_applies_capped_bonus_when_ready(monkeypatch) -> None:
    monkeypatch.setattr(ranking, "get_settings", lambda: _settings(ranking_enabled=True))
    candidate = main_force_candidate(main_force_advice=_advice(action="buy_confirmed", score=100.0, confidence=0.9))

    assert main_force_rank_bonus(candidate, shadow_status={"promotion_ready": True}) == 4.0


def test_main_force_ranking_blocks_fallback_distribution_and_risk(monkeypatch) -> None:
    monkeypatch.setattr(ranking, "get_settings", lambda: _settings(ranking_enabled=True))

    assert main_force_rank_bonus(
        main_force_candidate(main_force_advice=_advice(fallback_reason="data_quality")),
        shadow_status={"promotion_ready": True},
    ) == 0.0
    assert main_force_rank_bonus(
        main_force_candidate(main_force_advice=_advice(stage="distribution_risk")),
        shadow_status={"promotion_ready": True},
    ) == 0.0
    assert main_force_rank_bonus(
        main_force_candidate(main_force_advice=_advice(risk_flags=["风险阻断"])),
        shadow_status={"promotion_ready": True},
    ) == 0.0


def _settings(*, ranking_enabled: bool) -> SimpleNamespace:
    return SimpleNamespace(
        main_force_model_enabled=True,
        main_force_model_ranking_enabled=ranking_enabled,
        main_force_model_allowed_strategies="volume_shrink",
        main_force_model_min_confidence=0.58,
        main_force_model_min_score=55.0,
        main_force_model_max_rank_bonus=4.0,
    )


def _advice(
    *,
    action: str = "buy_probe",
    stage: str = "washout",
    score: float = 68.5,
    confidence: float = 0.685,
    risk_flags: list[str] | None = None,
    fallback_reason: str | None = None,
) -> dict:
    return {
        "stage": stage,
        "action": action,
        "score": score,
        "confidence": confidence,
        "risk_flags": risk_flags or [],
        "fallback_reason": fallback_reason,
    }
