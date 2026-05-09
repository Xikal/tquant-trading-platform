from __future__ import annotations

from app.services.low_buy.shared import LOW_BUY_RESULT_VERSION, LowBuyCandidateOut, json
from app.services.low_buy.strategy_policy import strong_buy_paused


def normalize_candidate_policy_state(candidate: LowBuyCandidateOut) -> LowBuyCandidateOut:
    if not strong_buy_paused(candidate.strategy_key):
        return candidate
    if candidate.buy_signal_state not in {"buy_now", "soft_buy_now"}:
        return candidate
    return candidate.model_copy(
        update={
            "buy_signal_state": "near_entry",
            "buy_signal_text": "接近买点",
            "buy_signal_hint": "该策略当前处于观察层，只保留接近买点提醒，不再给确定买入信号。",
        }
    )


def safe_json_object(raw: str | dict | None) -> dict:
    if isinstance(raw, dict):
        return raw
    try:
        payload = json.loads(raw or "{}")
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def safe_json_list(raw: str | list | None) -> list:
    if isinstance(raw, list):
        return raw
    try:
        payload = json.loads(raw or "[]")
    except Exception:
        return []
    return payload if isinstance(payload, list) else []


def response_payload_is_current(payload_source: str | dict) -> bool:
    payload = load_json_object(payload_source)
    if payload is None or not summary_filters_are_current(payload.get("filters")):
        return False
    candidates = list(payload.get("confirmed_candidates") or []) + list(payload.get("candidates") or [])
    history_sections = payload.get("history_sections") or []
    for section in history_sections:
        if not isinstance(section, dict):
            return False
        candidates.extend(section.get("candidates") or [])
    return all(candidate_payload_is_current(candidate) for candidate in candidates)


def summary_filters_are_current(summary_filters: dict | None) -> bool:
    required_keys = (
        "market_regime",
        "market_state",
        "market_state_strength",
        "regime_confidence",
        "state_persistence_days",
        "transition_risk",
        "breadth_ready",
        "emotion_ready",
        "market_bonus",
        "hot_industries_json",
        "hot_industry_source",
        "hot_industry_source_text",
        "limit_up_count",
        "board_height",
        "promotion_ratio",
        "broken_board_ratio",
        "high_flyer_retreat_ratio",
        "stock_up_ratio",
        "stock_median_change",
        "style_divergence",
        "hot_turnover",
        "hot_overlap_ratio",
        "previous_board_height",
        "promotion_break_gap",
        "promotion_break_pressure",
        "high_flyer_gap_speed",
        "distribution_pressure",
        "mainline_lifecycle_state",
        "mainline_lifecycle_text",
        "structure_mode",
    )
    return (
        isinstance(summary_filters, dict)
        and summary_filters.get("_result_version") == LOW_BUY_RESULT_VERSION
        and all(key in summary_filters for key in required_keys)
    )


def load_json_object(payload_source: str | dict) -> dict | None:
    if isinstance(payload_source, dict):
        return payload_source
    try:
        payload = json.loads(payload_source or "{}")
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def candidate_payload_is_current(payload_source: str | dict) -> bool:
    payload = load_json_object(payload_source)
    if payload is None:
        return False
    required_keys = (
        "payload_version",
        "market_state",
        "industry_tier",
        "risk_position_multiplier",
        "market_position_multiplier",
        "industry_position_multiplier",
        "dynamic_position_multiplier",
        "distribution_risk_score",
        "risk_tier",
        "false_breakout_flag",
        "stall_after_volume_flag",
        "intraday_reversal_flag",
        "dynamic_threshold_adjustment",
        "hard_risk",
        "exit_plan",
        "next_day_event_plan",
        "research_stage",
        "research_failed_rules",
        "research_near_miss_rules",
    )
    if payload.get("payload_version") != LOW_BUY_RESULT_VERSION:
        return False
    if not all(key in payload for key in required_keys):
        return False
    try:
        LowBuyCandidateOut.model_validate(payload)
    except Exception:
        return False
    return True
