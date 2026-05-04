from __future__ import annotations


_DEFAULT_SCORE_PENALTY_CAP = 8.0
_STATE_SCORE_PENALTY_CAPS = {
    "broad_rally": 5.5,
    "repair": 6.5,
    "weight_support_active": 7.5,
    "low_volume_wait": 8.0,
    "fast_rotation": 8.8,
    "weight_support": 9.0,
    "high_flyer_retreat": 10.0,
    "risk_release": 11.0,
}


def cap_candidate_score_penalty(
    *,
    score_penalty: float,
    market_state: str,
    execution_blocked: bool,
) -> tuple[float, bool]:
    """Cap non-blocking contextual penalties so one risk is not counted repeatedly."""

    if execution_blocked:
        return round(score_penalty, 2), False
    cap = _STATE_SCORE_PENALTY_CAPS.get(market_state, _DEFAULT_SCORE_PENALTY_CAP)
    capped = min(score_penalty, cap)
    return round(capped, 2), capped < score_penalty
