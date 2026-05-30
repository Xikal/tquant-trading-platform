from __future__ import annotations

from types import SimpleNamespace

from app.models.schema_defs.market import SectorRelativeStrengthItem, SectorRelativeStrengthResponse
from app.services.decision_context.sector_leader_gate import (
    SectorLeaderGateInput,
    apply_sector_leader_gate_to_score,
    enrich_sector_relative_strength_response,
    evaluate_sector_leader_gate,
)


def test_sector_leader_gate_allows_broad_sector_with_healthy_leader() -> None:
    result = evaluate_sector_leader_gate(
        SectorLeaderGateInput(
            strategy_key="first_board",
            sector_rank=1,
            sector_strength_score=86.0,
            leader_score=88.0,
            leader_rank=1,
            same_sector_limit_up_count=5,
            diffusion_score=82.0,
            turnover_confirmation_score=78.0,
        )
    )

    assert result.decision == "allow"
    assert result.score >= 75
    assert result.evidence["leader_status"] == "healthy"


def test_sector_leader_gate_reduces_isolated_theme() -> None:
    result = evaluate_sector_leader_gate(
        SectorLeaderGateInput(
            strategy_key="first_board",
            sector_rank=11,
            sector_strength_score=35.0,
            leader_score=48.0,
            leader_rank=9,
            same_sector_limit_up_count=0,
            diffusion_score=18.0,
            turnover_confirmation_score=34.0,
        )
    )

    assert result.decision == "reduce"
    assert "孤立" in " ".join(result.reasons) or "扩散不足" in " ".join(result.reasons)


def test_sector_leader_gate_boost_caps_core_aux_and_never_boosts_research() -> None:
    gate = evaluate_sector_leader_gate(
        SectorLeaderGateInput(
            strategy_key="first_board",
            sector_rank=1,
            sector_strength_score=92.0,
            leader_score=94.0,
            leader_rank=1,
            same_sector_limit_up_count=7,
            diffusion_score=88.0,
            turnover_confirmation_score=86.0,
        )
    )

    core_score, core_boost = apply_sector_leader_gate_to_score(70.0, gate, "first_board")
    aux_score, aux_boost = apply_sector_leader_gate_to_score(70.0, gate, "late_session_strong_support")
    research_score, research_boost = apply_sector_leader_gate_to_score(None, gate, "n_pattern_long_wash")

    assert core_boost <= 12.0
    assert core_score == 70.0 + core_boost
    assert aux_boost <= 6.0
    assert aux_score == 70.0 + aux_boost
    assert research_score is None
    assert research_boost == 0.0


def test_sector_relative_strength_response_is_enriched_with_gate_fields() -> None:
    response = SectorRelativeStrengthResponse(
        updated_at="2026-05-30 10:30:00",
        trade_date="2026-05-30",
        sector_count=1,
        items=[
            SectorRelativeStrengthItem(
                sector_name="半导体",
                symbol="000001",
                name="测试股份",
                latest_price=10.0,
                change_pct=5.2,
                sector_median_change_pct=2.1,
                volume_ratio=2.3,
                turnover_proxy=2.0,
                leader_score=86.0,
                rank=1,
            )
        ],
    )

    enriched = enrich_sector_relative_strength_response(
        response,
        market_context=SimpleNamespace(hot_industries=["半导体"], limit_up_count=78),
    )
    item = enriched.items[0]

    assert item.leader_status == "healthy"
    assert item.same_sector_limit_up_count >= 1
    assert item.diffusion_score >= 70
    assert item.sector_leader_gate_decision == "allow"
