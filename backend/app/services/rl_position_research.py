from __future__ import annotations

from app.services.position_policy_research import (
    LEGACY_POSITION_POLICY_ALIAS,
    POSITION_POLICY_ALGORITHM,
    _position_from_edge,
    run_position_policy_research,
)


def run_offline_position_research(db, run_id: int) -> dict:  # noqa: ANN001
    return run_position_policy_research(db, run_id)


__all__ = [
    "LEGACY_POSITION_POLICY_ALIAS",
    "POSITION_POLICY_ALGORITHM",
    "_position_from_edge",
    "run_offline_position_research",
]
