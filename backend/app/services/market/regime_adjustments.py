from __future__ import annotations

from dataclasses import replace

from app.services.market.regime_helpers import transition_risk as calculate_transition_risk
from app.services.market.regime_scoring import clone_snapshot_with_state
from app.services.market.regime_types import MarketRegimeSnapshot


def stabilize_market_regime(
    snapshot: MarketRegimeSnapshot,
    previous_snapshot: MarketRegimeSnapshot | None,
) -> MarketRegimeSnapshot:
    if previous_snapshot is None or previous_snapshot.state == snapshot.state:
        return snapshot
    if abs(snapshot.regime_score - previous_snapshot.regime_score) >= 6.0:
        return snapshot
    if previous_snapshot.state_strength < snapshot.state_strength:
        return snapshot
    return clone_snapshot_with_state(
        snapshot,
        state=previous_snapshot.state,
        state_strength=previous_snapshot.state_strength,
        regime_score=previous_snapshot.regime_score,
    )


def apply_regime_continuity(
    snapshot: MarketRegimeSnapshot,
    previous_snapshot: MarketRegimeSnapshot | None,
) -> MarketRegimeSnapshot:
    if previous_snapshot is None:
        return snapshot
    transition_risk = calculate_transition_risk(snapshot, previous_snapshot)
    persistence_days = previous_snapshot.state_persistence_days if snapshot.state == previous_snapshot.state else 1
    confidence = max(0.0, min(1.0, snapshot.regime_confidence - transition_risk * 0.18))
    return replace(
        snapshot,
        state_persistence_days=max(1, persistence_days),
        transition_risk=transition_risk,
        regime_confidence=round(confidence, 4),
    )


def apply_market_readiness_guard(snapshot: MarketRegimeSnapshot) -> MarketRegimeSnapshot:
    if snapshot.breadth_ready and snapshot.emotion_ready:
        return snapshot
    if snapshot.state not in guarded_states():
        return snapshot
    return clone_snapshot_with_state(
        snapshot,
        state="low_volume_wait",
        state_strength=min(snapshot.state_strength, 0.35),
        regime_score=min(snapshot.regime_score, 42.0),
        description_suffix="环境快照仍在补齐，先按中性偏防守处理。",
    )


def guarded_states() -> set[str]:
    return {
        "broad_rally",
        "repair",
        "weight_support",
        "weight_support_active",
        "high_flyer_retreat",
        "risk_release",
    }
