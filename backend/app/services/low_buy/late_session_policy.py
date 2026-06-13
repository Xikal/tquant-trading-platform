from __future__ import annotations

from app.services.low_buy.strategy_policy import (
    CORE_STRATEGIES,
    LOW_SAMPLE_CAPPED_STRATEGIES,
    get_strategy_tier,
)

FORMAL_LATE_SESSION_STRATEGIES = frozenset(
    {
        "first_board",
        "volume_shrink",
        "late_session_strong_support",
    }
)
LATE_SESSION_LOW_SAMPLE_CAPPED_STRATEGIES = frozenset({"late_session_strong_support"})
LATE_SESSION_DEFAULT_LIMIT = 12
LATE_SESSION_SOURCE_CANDIDATE_LIMIT = 30


def late_session_strategy_allowed_for_formal(strategy_key: str) -> bool:
    return str(strategy_key or "") in FORMAL_LATE_SESSION_STRATEGIES


def classify_late_session_strategy(strategy_key: str) -> str:
    normalized = str(strategy_key or "")
    if normalized in LATE_SESSION_LOW_SAMPLE_CAPPED_STRATEGIES or normalized in LOW_SAMPLE_CAPPED_STRATEGIES:
        return "auxiliary_capped"
    if normalized in CORE_STRATEGIES:
        return "core"
    if late_session_strategy_allowed_for_formal(normalized):
        return str(get_strategy_tier(normalized).value)
    return "research_only"


def late_session_score_cap(strategy_key: str, raw_score: float | int | None) -> float:
    try:
        score = float(raw_score or 0.0)
    except (TypeError, ValueError):
        score = 0.0
    score = max(0.0, min(score, 100.0))
    if str(strategy_key or "") in LATE_SESSION_LOW_SAMPLE_CAPPED_STRATEGIES:
        return min(score, 72.0)
    return score
