from __future__ import annotations


def base_state_scores(**values: float) -> dict[str, float]:
    persistent_hot_pressure = _normalize(1.0 - values["hot_turnover"], 0.10, 0.90)
    wait_pressure = _average(
        _normalize(abs(values["median_change"]), 0.0, 0.55),
        _normalize(abs(values["stock_median_change"]), 0.0, 0.9),
        _normalize(values["top3_avg_change"], 0.0, 0.75),
        _normalize(0.55 - values["positive_ratio"], 0.0, 0.28),
    )
    return {
        "broad_rally": _clamp_score(
            values["breadth_strength"] * 0.72
            + _normalize(0.26 - values["hot_turnover"], -0.25, 0.26) * 0.16
            + _normalize(18.0 - values["limit_down_value"], -10.0, 18.0) * 0.12
            + values["emotion_strength"] * 0.10
        ),
        "weight_support": _clamp_score(
            values["weight_support_pressure"] * 0.68
            + _normalize(0.46 - values["positive_ratio"], -0.08, 0.22) * 0.18
            + _normalize(0.50 - values["stock_up_ratio"], -0.08, 0.26) * 0.14
            + persistent_hot_pressure * 0.08
            - values["emotion_strength"] * 0.08
        ),
        "weight_support_active": _clamp_score(
            values["weight_support_pressure"] * 0.48
            + values["emotion_strength"] * 0.20
            + _normalize(values["hot_turnover"], 0.10, 0.58) * 0.10
            + _normalize(values["limit_up_count"], 10.0, 55.0) * 0.10
            + _normalize(0.52 - values["stock_up_ratio"], -0.06, 0.24) * 0.12
            + _normalize(values["hot_overlap_ratio"], 0.12, 0.60) * 0.10
            + _normalize(values["promotion_break_gap"], -0.06, 0.18) * 0.10
            + _normalize(65.0 - values["distribution_pressure"], 0.0, 65.0) * 0.08
            - values["retreat_pressure"] * 0.08
        ),
        "low_volume_wait": _clamp_score(
            wait_pressure * 0.70
            + _normalize(0.25 - values["top3_avg_change"], -0.55, 0.35) * 0.18
            + _normalize(16.0 - values["limit_down_value"], -12.0, 16.0) * 0.12
        ),
        "fast_rotation": _clamp_score(
            values["rotation_pressure"] * 0.76
            + _normalize(0.62 - values["stock_up_ratio"], 0.0, 0.30) * 0.12
            + _normalize(28.0 - values["limit_down_value"], -16.0, 28.0) * 0.12
            + _normalize(1.6 - values["style_divergence"], -0.4, 1.6) * 0.08
            + _normalize(0.50 - values["hot_overlap_ratio"], 0.0, 0.50) * 0.12
            + values["emotion_strength"] * 0.08
        ),
        "high_flyer_retreat": _clamp_score(
            values["risk_pressure"] * 0.52
            + _normalize(values["limit_down_value"], 10.0, 36.0) * 0.18
            + _normalize(-values["smallcap_change"], -0.10, 2.20) * 0.18
            + _normalize(0.48 - values["positive_ratio"], -0.05, 0.28) * 0.12
            + values["retreat_pressure"] * 0.18
            + _normalize(values["distribution_pressure"], 28.0, 88.0) * 0.10
        ),
        "repair": _clamp_score(
            values["breadth_strength"] * 0.48
            + _normalize(values["top3_avg_change"], 0.40, 1.20) * 0.16
            + _normalize(values["stock_median_change"], -0.20, 0.80) * 0.18
            + _normalize(26.0 - values["limit_down_value"], -10.0, 26.0) * 0.18
            + values["emotion_strength"] * 0.10
            + _normalize(values["promotion_break_gap"], -0.08, 0.20) * 0.10
            + _normalize(75.0 - values["distribution_pressure"], 0.0, 75.0) * 0.08
        ),
        "risk_release": _clamp_score(
            values["risk_pressure"] * 0.68
            + _normalize(values["limit_down_value"], 22.0, 65.0) * 0.18
            + _normalize(-values["stock_median_change"], 0.0, 3.0) * 0.14
            + values["retreat_pressure"] * 0.16
            + _normalize(values["distribution_pressure"], 35.0, 92.0) * 0.12
        ),
    }


def apply_score_adjustments(scores: dict[str, float], **values: float | bool) -> None:
    if values["positive_ratio"] < 0.28 and values["stock_up_ratio"] < 0.32:
        scores["risk_release"] += 8.0
    if values["defensive_lead"] and values["style_divergence"] > 1.0 and values["stock_up_ratio"] < 0.46:
        scores["weight_support"] += 6.0
    if values["defensive_lead"] and values["emotion_strength"] >= 42.0 and values["retreat_pressure"] <= 52.0:
        scores["weight_support_active"] += 6.0
    if values["hot_turnover"] >= 0.55 and values["style_divergence"] < 1.1:
        scores["fast_rotation"] += 6.0
        scores["weight_support"] -= 3.0
        scores["weight_support_active"] -= 2.5
    if values["hot_overlap_ratio"] <= 0.18 and values["hot_turnover"] >= 0.45:
        scores["fast_rotation"] += 5.5
        scores["repair"] -= 2.5
        scores["weight_support_active"] -= 2.0
    if values["hot_overlap_ratio"] >= 0.45 and values["hot_turnover"] <= 0.30:
        scores["fast_rotation"] -= 4.0
        scores["weight_support_active"] += 3.0
        scores["repair"] += 1.5
    if values["defensive_lead"] and values["style_divergence"] >= 1.4 and values["hot_turnover"] <= 0.35:
        scores["weight_support"] += 4.0
        scores["fast_rotation"] -= 3.0
    if values["high_flyer_retreat_ratio"] >= 0.24 or values["broken_board_ratio"] >= 0.32:
        scores["high_flyer_retreat"] += 5.0
        scores["risk_release"] += 3.5
    if values["high_flyer_gap_speed"] >= 0.40 or values["promotion_break_gap"] <= -0.08:
        scores["high_flyer_retreat"] += 6.0
        scores["risk_release"] += 3.0
        scores["repair"] -= 2.5
    if values["promotion_ratio"] >= 0.38 and values["board_height"] >= 3 and values["stock_up_ratio"] >= 0.42:
        scores["repair"] += 4.0
        scores["broad_rally"] += 3.0
    if not values["breadth_ready"]:
        scores["repair"] -= 8.0
        scores["broad_rally"] -= 10.0
        scores["weight_support"] -= 4.0
        scores["weight_support_active"] -= 5.0
    if not values["emotion_ready"]:
        scores["fast_rotation"] -= 3.0
        scores["high_flyer_retreat"] -= 4.0
    scores["high_flyer_retreat"] += _normalize(values["previous_board_height"] - values["board_height"], 0.0, 3.0) * 0.10
    scores["high_flyer_retreat"] += _normalize(values["previous_limit_up_count"] - values["limit_up_count"], -6.0, 30.0) * 0.08


def _average(*values: float) -> float:
    return sum(values) / max(len(values), 1)


def _normalize(value: float, low: float, high: float) -> float:
    if high <= low:
        return 0.0
    clipped = min(max(value, low), high)
    return (clipped - low) / (high - low) * 100.0


def _clamp_score(value: float) -> float:
    return max(0.0, min(100.0, value))
