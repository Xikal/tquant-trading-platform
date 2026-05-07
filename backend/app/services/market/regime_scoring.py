from __future__ import annotations

import pandas as pd

from app.services.market.emotion import MarketEmotionSnapshot
from app.services.market.regime_types import (
    DEFENSIVE_KEYWORDS,
    STATE_CONFIG,
    MarketBreadthSnapshot,
    MarketRegimeSnapshot,
)
from app.services.market.regime_score_rules import (
    apply_score_adjustments,
    base_state_scores,
)


def classify_market_regime(
    board_frame: pd.DataFrame | None,
    *,
    limit_down_count: int | None,
    hot_industries: list[str],
    hot_industry_source: str,
    hot_industry_source_text: str,
    breadth_snapshot: MarketBreadthSnapshot | None = None,
    emotion_snapshot: MarketEmotionSnapshot | None = None,
) -> MarketRegimeSnapshot:
    positive_ratio, top3_avg_change, median_change, defensive_lead = _industry_context(
        board_frame,
        hot_industries,
    )
    if board_frame is not None and not board_frame.empty and not hot_industries:
        hot_industries = board_frame.head(3)["industry"].tolist()
        defensive_lead = _has_defensive_lead(hot_industries)

    breadth = breadth_snapshot or _empty_breadth_snapshot()
    emotion = emotion_snapshot or _empty_emotion_snapshot()
    retreat_pressure = _retreat_pressure(
        emotion_ready=emotion.emotion_ready,
        high_flyer_retreat_ratio=emotion.high_flyer_retreat_ratio,
        broken_board_ratio=emotion.broken_board_ratio,
        limit_down_value=float(limit_down_count or 0),
        promotion_break_pressure=emotion.promotion_break_pressure,
        high_flyer_gap_speed=emotion.high_flyer_gap_speed,
    )
    distribution_pressure = _composite_distribution_pressure(
        emotion_ready=emotion.emotion_ready,
        retreat_pressure=retreat_pressure,
        high_flyer_gap_speed=emotion.high_flyer_gap_speed,
        promotion_break_pressure=emotion.promotion_break_pressure,
        stock_up_ratio=breadth.stock_up_ratio,
    )
    mainline_state, mainline_text = _mainline_lifecycle(
        hot_industries=hot_industries,
        hot_overlap_ratio=breadth.hot_overlap_ratio,
        hot_turnover=breadth.hot_turnover,
        limit_up_count=emotion.limit_up_count,
        previous_limit_up_count=emotion.previous_limit_up_count,
        board_height=emotion.board_height,
        previous_board_height=emotion.previous_board_height,
        promotion_ratio=emotion.promotion_ratio,
        high_flyer_retreat_ratio=emotion.high_flyer_retreat_ratio,
        distribution_pressure=distribution_pressure,
    )
    state_scores = build_state_scores(
        breadth_ready=breadth.breadth_ready,
        emotion_ready=emotion.emotion_ready,
        positive_ratio=positive_ratio,
        top3_avg_change=top3_avg_change,
        median_change=median_change,
        limit_down_count=limit_down_count,
        defensive_lead=defensive_lead,
        stock_up_ratio=breadth.stock_up_ratio,
        stock_median_change=breadth.stock_median_change,
        style_divergence=breadth.style_divergence,
        hot_turnover=breadth.hot_turnover,
        hot_overlap_ratio=breadth.hot_overlap_ratio,
        concentration=top3_avg_change - median_change,
        smallcap_change=breadth.smallcap_change,
        largecap_change=breadth.largecap_change,
        limit_up_count=emotion.limit_up_count,
        previous_limit_up_count=emotion.previous_limit_up_count,
        board_height=emotion.board_height,
        previous_board_height=emotion.previous_board_height,
        promotion_ratio=emotion.promotion_ratio,
        broken_board_ratio=emotion.broken_board_ratio,
        promotion_break_gap=emotion.promotion_break_gap,
        promotion_break_pressure=emotion.promotion_break_pressure,
        high_flyer_retreat_ratio=emotion.high_flyer_retreat_ratio,
        high_flyer_gap_speed=emotion.high_flyer_gap_speed,
    )
    state, regime_score = _select_state(state_scores)
    config = STATE_CONFIG[state]
    return MarketRegimeSnapshot(
        state=state,
        label=config["label"],
        description=config["description"],
        ranking_bonus=config["ranking_bonus"],
        position_multiplier=config["position_multiplier"],
        buy_signal_penalty=config["buy_signal_penalty"],
        t_threshold_shift=config["t_threshold_shift"],
        positive_threshold_shift=config["positive_threshold_shift"],
        negative_threshold_shift=config["negative_threshold_shift"],
        hot_industries=hot_industries,
        hot_industry_source=hot_industry_source,
        hot_industry_source_text=hot_industry_source_text,
        limit_down_count=limit_down_count,
        breadth_ready=breadth.breadth_ready,
        emotion_ready=emotion.emotion_ready,
        positive_industry_ratio=positive_ratio,
        top3_avg_change=top3_avg_change,
        median_change=median_change,
        defensive_lead=defensive_lead,
        stock_up_ratio=breadth.stock_up_ratio,
        stock_median_change=breadth.stock_median_change,
        largecap_change=breadth.largecap_change,
        smallcap_change=breadth.smallcap_change,
        style_divergence=breadth.style_divergence,
        hot_turnover=breadth.hot_turnover,
        hot_overlap_ratio=breadth.hot_overlap_ratio,
        limit_up_count=emotion.limit_up_count,
        previous_limit_up_count=emotion.previous_limit_up_count,
        board_height=emotion.board_height,
        previous_board_height=emotion.previous_board_height,
        promotion_ratio=emotion.promotion_ratio,
        broken_board_ratio=emotion.broken_board_ratio,
        promotion_break_gap=emotion.promotion_break_gap,
        promotion_break_pressure=emotion.promotion_break_pressure,
        high_flyer_retreat_ratio=emotion.high_flyer_retreat_ratio,
        high_flyer_gap_speed=emotion.high_flyer_gap_speed,
        distribution_pressure=distribution_pressure,
        mainline_lifecycle_state=mainline_state,
        mainline_lifecycle_text=mainline_text,
        state_strength=round(_clamp(regime_score / 100.0), 4),
        regime_score=round(regime_score, 2),
        regime_confidence=_regime_confidence(
            regime_score=regime_score,
            breadth_ready=breadth.breadth_ready,
            emotion_ready=emotion.emotion_ready,
            distribution_pressure=distribution_pressure,
        ),
        state_persistence_days=1,
        transition_risk=0.0,
    )


def build_state_scores(
    *,
    breadth_ready: bool,
    emotion_ready: bool,
    positive_ratio: float,
    top3_avg_change: float,
    median_change: float,
    limit_down_count: int | None,
    defensive_lead: bool,
    stock_up_ratio: float,
    stock_median_change: float,
    style_divergence: float,
    hot_turnover: float,
    hot_overlap_ratio: float,
    concentration: float,
    smallcap_change: float,
    largecap_change: float,
    limit_up_count: int,
    previous_limit_up_count: int,
    board_height: int,
    previous_board_height: int,
    promotion_ratio: float,
    broken_board_ratio: float,
    promotion_break_gap: float,
    promotion_break_pressure: float,
    high_flyer_retreat_ratio: float,
    high_flyer_gap_speed: float,
) -> dict[str, float]:
    params = _regime_scoring_params()
    limit_down_value = float(limit_down_count or 0)
    breadth_strength = _average(
        _normalize_with_params(params, "positive_ratio", positive_ratio),
        _normalize_with_params(params, "stock_up_ratio", stock_up_ratio),
        _normalize_with_params(params, "top3_avg_change", top3_avg_change),
        _normalize_with_params(params, "median_change", median_change),
        _normalize_with_params(params, "stock_median_change", stock_median_change),
    )
    risk_pressure = _average(
        _normalize_with_params(params, "limit_down_value", limit_down_value),
        _normalize_with_params(params, "negative_median_change", -median_change),
        _normalize_with_params(params, "negative_stock_median_change", -stock_median_change),
        _normalize_with_params(params, "weak_stock_up_gap", 0.52 - stock_up_ratio),
    )
    weight_pressure = _average(
        _normalize_with_params(params, "style_divergence", style_divergence),
        _normalize_with_params(params, "largecap_change", largecap_change),
        _normalize_with_params(params, "negative_smallcap_change", -smallcap_change),
        _normalize_with_params(params, "weight_stock_up_gap", 0.52 - stock_up_ratio),
        100.0 if defensive_lead else 0.0,
    )
    rotation_pressure = _average(
        _normalize_with_params(params, "concentration", concentration),
        _normalize_with_params(params, "hot_turnover", hot_turnover),
        _normalize_with_params(params, "hot_overlap_gap", 0.58 - hot_overlap_ratio),
        _normalize_with_params(params, "rotation_top3_change", top3_avg_change),
        _normalize_with_params(params, "rotation_positive_ratio", positive_ratio),
    )
    emotion_strength = _emotion_strength(
        emotion_ready,
        limit_up_count,
        board_height,
        promotion_ratio,
        promotion_break_gap,
    )
    retreat_pressure = _retreat_pressure(
        emotion_ready=emotion_ready,
        high_flyer_retreat_ratio=high_flyer_retreat_ratio,
        broken_board_ratio=broken_board_ratio,
        limit_down_value=limit_down_value,
        promotion_break_pressure=promotion_break_pressure,
        high_flyer_gap_speed=high_flyer_gap_speed,
    )
    distribution_pressure = _composite_distribution_pressure(
        emotion_ready=emotion_ready,
        retreat_pressure=retreat_pressure,
        high_flyer_gap_speed=high_flyer_gap_speed,
        promotion_break_pressure=promotion_break_pressure,
        stock_up_ratio=stock_up_ratio,
    )
    scores = base_state_scores(
        breadth_strength=breadth_strength,
        risk_pressure=risk_pressure,
        weight_support_pressure=weight_pressure,
        rotation_pressure=rotation_pressure,
        emotion_strength=emotion_strength,
        retreat_pressure=retreat_pressure,
        distribution_pressure=distribution_pressure,
        limit_down_value=limit_down_value,
        positive_ratio=positive_ratio,
        top3_avg_change=top3_avg_change,
        median_change=median_change,
        stock_up_ratio=stock_up_ratio,
        stock_median_change=stock_median_change,
        style_divergence=style_divergence,
        hot_turnover=hot_turnover,
        hot_overlap_ratio=hot_overlap_ratio,
        smallcap_change=smallcap_change,
        limit_up_count=limit_up_count,
        board_height=board_height,
        promotion_break_gap=promotion_break_gap,
    )
    apply_score_adjustments(
        scores,
        breadth_ready=breadth_ready,
        emotion_ready=emotion_ready,
        positive_ratio=positive_ratio,
        stock_up_ratio=stock_up_ratio,
        defensive_lead=defensive_lead,
        style_divergence=style_divergence,
        hot_turnover=hot_turnover,
        hot_overlap_ratio=hot_overlap_ratio,
        emotion_strength=emotion_strength,
        retreat_pressure=retreat_pressure,
        limit_up_count=limit_up_count,
        board_height=board_height,
        promotion_ratio=promotion_ratio,
        high_flyer_retreat_ratio=high_flyer_retreat_ratio,
        broken_board_ratio=broken_board_ratio,
        high_flyer_gap_speed=high_flyer_gap_speed,
        promotion_break_gap=promotion_break_gap,
        previous_board_height=previous_board_height,
        previous_limit_up_count=previous_limit_up_count,
        limit_down_value=limit_down_value,
    )
    return {key: _clamp_score(value) for key, value in scores.items()}


def market_regime_text(snapshot: MarketRegimeSnapshot) -> str:
    parts = [f"市场状态：{snapshot.label}"]
    if snapshot.positive_industry_ratio > 0:
        parts.append(f"行业上涨占比 {snapshot.positive_industry_ratio * 100:.0f}%")
    if snapshot.stock_up_ratio > 0:
        parts.append(f"个股上涨占比 {snapshot.stock_up_ratio * 100:.0f}%")
    if snapshot.limit_down_count is not None:
        parts.append(f"跌停 {snapshot.limit_down_count} 家")
    if snapshot.emotion_ready:
        parts.append(f"连板高度 {snapshot.board_height} 板")
        parts.append(f"主线重合 {snapshot.hot_overlap_ratio * 100:.0f}%")
        parts.append(f"派发压力 {snapshot.distribution_pressure:.0f}%")
    if snapshot.mainline_lifecycle_text:
        parts.append(snapshot.mainline_lifecycle_text)
    return " · ".join(parts)


def normalize_board_frame(frame: pd.DataFrame | None) -> pd.DataFrame | None:
    if frame is None or frame.empty:
        return None
    normalized = frame.rename(columns={"板块名称": "industry", "涨跌幅": "change_pct"}).copy()
    normalized["change_pct"] = pd.to_numeric(normalized["change_pct"], errors="coerce")
    normalized = normalized.dropna(subset=["change_pct"])
    if normalized.empty:
        return None
    return normalized.sort_values("change_pct", ascending=False).reset_index(drop=True)


def clone_snapshot_with_state(
    snapshot: MarketRegimeSnapshot,
    *,
    state: str,
    state_strength: float | None = None,
    regime_score: float | None = None,
    description_suffix: str = "",
) -> MarketRegimeSnapshot:
    config = STATE_CONFIG[state]
    description = config["description"]
    if description_suffix:
        description = f"{description} {description_suffix}"
    return MarketRegimeSnapshot(
        state=state,
        label=config["label"],
        description=description,
        ranking_bonus=config["ranking_bonus"],
        position_multiplier=config["position_multiplier"],
        buy_signal_penalty=config["buy_signal_penalty"],
        t_threshold_shift=config["t_threshold_shift"],
        positive_threshold_shift=config["positive_threshold_shift"],
        negative_threshold_shift=config["negative_threshold_shift"],
        hot_industries=snapshot.hot_industries,
        hot_industry_source=snapshot.hot_industry_source,
        hot_industry_source_text=snapshot.hot_industry_source_text,
        limit_down_count=snapshot.limit_down_count,
        breadth_ready=snapshot.breadth_ready,
        emotion_ready=snapshot.emotion_ready,
        positive_industry_ratio=snapshot.positive_industry_ratio,
        top3_avg_change=snapshot.top3_avg_change,
        median_change=snapshot.median_change,
        defensive_lead=snapshot.defensive_lead,
        stock_up_ratio=snapshot.stock_up_ratio,
        stock_median_change=snapshot.stock_median_change,
        largecap_change=snapshot.largecap_change,
        smallcap_change=snapshot.smallcap_change,
        style_divergence=snapshot.style_divergence,
        hot_turnover=snapshot.hot_turnover,
        hot_overlap_ratio=snapshot.hot_overlap_ratio,
        limit_up_count=snapshot.limit_up_count,
        previous_limit_up_count=snapshot.previous_limit_up_count,
        board_height=snapshot.board_height,
        previous_board_height=snapshot.previous_board_height,
        promotion_ratio=snapshot.promotion_ratio,
        broken_board_ratio=snapshot.broken_board_ratio,
        promotion_break_gap=snapshot.promotion_break_gap,
        promotion_break_pressure=snapshot.promotion_break_pressure,
        high_flyer_retreat_ratio=snapshot.high_flyer_retreat_ratio,
        high_flyer_gap_speed=snapshot.high_flyer_gap_speed,
        distribution_pressure=snapshot.distribution_pressure,
        mainline_lifecycle_state=snapshot.mainline_lifecycle_state,
        mainline_lifecycle_text=snapshot.mainline_lifecycle_text,
        state_strength=snapshot.state_strength if state_strength is None else round(_clamp(state_strength), 4),
        regime_score=snapshot.regime_score if regime_score is None else round(max(0.0, min(100.0, regime_score)), 2),
        regime_confidence=snapshot.regime_confidence,
        state_persistence_days=snapshot.state_persistence_days,
        transition_risk=snapshot.transition_risk,
    )


def _industry_context(
    board_frame: pd.DataFrame | None,
    hot_industries: list[str],
) -> tuple[float, float, float, bool]:
    defensive_lead = _has_defensive_lead(hot_industries)
    if board_frame is None or board_frame.empty:
        return 0.0, 0.0, 0.0, defensive_lead
    return (
        round(float((board_frame["change_pct"] > 0).mean()), 4),
        round(float(board_frame.head(3)["change_pct"].mean()), 4),
        round(float(board_frame["change_pct"].median()), 4),
        defensive_lead,
    )


def _has_defensive_lead(hot_industries: list[str]) -> bool:
    return any(
        any(keyword in industry for keyword in DEFENSIVE_KEYWORDS)
        for industry in hot_industries
    )


def _empty_breadth_snapshot() -> MarketBreadthSnapshot:
    return MarketBreadthSnapshot(
        breadth_ready=False,
        stock_up_ratio=0.0,
        stock_median_change=0.0,
        largecap_change=0.0,
        smallcap_change=0.0,
        style_divergence=0.0,
        hot_turnover=0.0,
        hot_overlap_ratio=0.0,
    )


def _empty_emotion_snapshot() -> MarketEmotionSnapshot:
    return MarketEmotionSnapshot(
        emotion_ready=False,
        limit_up_count=0,
        previous_limit_up_count=0,
        board_height=0,
        previous_board_height=0,
        promotion_ratio=0.0,
        broken_board_ratio=0.0,
        promotion_break_gap=0.0,
        promotion_break_pressure=0.0,
        high_flyer_retreat_ratio=0.0,
        high_flyer_gap_speed=0.0,
        emotion_distribution_pressure=0.0,
    )


def _emotion_strength(
    emotion_ready: bool,
    limit_up_count: int,
    board_height: int,
    promotion_ratio: float,
    promotion_break_gap: float,
) -> float:
    if not emotion_ready:
        return 0.0
    params = _regime_scoring_params()
    return _average(
        _normalize_with_params(params, "limit_up_count", limit_up_count),
        _normalize_with_params(params, "board_height", board_height),
        _normalize_with_params(params, "promotion_ratio", promotion_ratio),
        _normalize_with_params(params, "promotion_break_gap", promotion_break_gap),
    )


def _retreat_pressure(
    *,
    emotion_ready: bool,
    high_flyer_retreat_ratio: float,
    broken_board_ratio: float,
    limit_down_value: float,
    promotion_break_pressure: float,
    high_flyer_gap_speed: float,
) -> float:
    if not emotion_ready:
        return 0.0
    params = _regime_scoring_params()
    return _average(
        _normalize_with_params(params, "high_flyer_retreat_ratio", high_flyer_retreat_ratio),
        _normalize_with_params(params, "broken_board_ratio", broken_board_ratio),
        _normalize_with_params(params, "retreat_limit_down_value", limit_down_value),
        _normalize_with_params(params, "promotion_break_pressure", promotion_break_pressure),
        _normalize_with_params(params, "high_flyer_gap_speed", high_flyer_gap_speed),
    )


def _composite_distribution_pressure(
    *,
    emotion_ready: bool,
    retreat_pressure: float,
    high_flyer_gap_speed: float,
    promotion_break_pressure: float,
    stock_up_ratio: float,
) -> float:
    if not emotion_ready:
        return 0.0
    params = _regime_scoring_params()
    return _average(
        retreat_pressure,
        _normalize_with_params(params, "high_flyer_gap_speed", high_flyer_gap_speed),
        _normalize_with_params(params, "promotion_break_pressure", promotion_break_pressure),
        _normalize_with_params(params, "distribution_stock_up_gap", 0.60 - stock_up_ratio),
    )


def _mainline_lifecycle(
    *,
    hot_industries: list[str],
    hot_overlap_ratio: float,
    hot_turnover: float,
    limit_up_count: int,
    previous_limit_up_count: int,
    board_height: int,
    previous_board_height: int,
    promotion_ratio: float,
    high_flyer_retreat_ratio: float,
    distribution_pressure: float,
) -> tuple[str, str]:
    params = _regime_scoring_params().get("mainline_lifecycle", {})
    if not hot_industries:
        return "unknown", "主线阶段：热点归因不足"
    if high_flyer_retreat_ratio >= _param_float(params, "retreat_high_flyer_ratio", 0.28) or distribution_pressure >= _param_float(params, "retreat_distribution_pressure", 62.0):
        return "retreat", "主线阶段：退潮风险"
    if hot_turnover >= _param_float(params, "rotation_hot_turnover", 0.55) or hot_overlap_ratio <= _param_float(params, "rotation_hot_overlap_max", 0.18):
        return "rotation", "主线阶段：轮动过快"
    if board_height >= _param_float(params, "accelerating_board_height", 4) and promotion_ratio >= _param_float(params, "accelerating_promotion_ratio", 0.32) and hot_overlap_ratio >= _param_float(params, "accelerating_hot_overlap", 0.38):
        return "accelerating", "主线阶段：加速延续"
    if limit_up_count > previous_limit_up_count and board_height >= max(previous_board_height, 2):
        return "warming", "主线阶段：修复升温"
    if hot_overlap_ratio >= _param_float(params, "stable_hot_overlap", 0.35):
        return "stable", "主线阶段：持续沉淀"
    return "scattered", "主线阶段：热点分散"


def _select_state(state_scores: dict[str, float]) -> tuple[str, float]:
    params = _regime_scoring_params().get("state_selection", {})
    ranked = sorted(state_scores.items(), key=lambda item: item[1], reverse=True)
    if not ranked:
        return "low_volume_wait", 0.0
    top_state, top_score = ranked[0]
    if len(ranked) == 1:
        return top_state, top_score
    second_state, second_score = ranked[1]
    if top_state == "repair" and second_state == "low_volume_wait" and top_score - second_score <= _param_float(params, "repair_low_volume_max_gap", 3.0):
        return second_state, second_score
    if top_state == "weight_support" and second_state == "weight_support_active" and top_score - second_score <= _param_float(params, "weight_support_active_max_gap", 4.0):
        return second_state, second_score
    return top_state, top_score


def _regime_confidence(
    *,
    regime_score: float,
    breadth_ready: bool,
    emotion_ready: bool,
    distribution_pressure: float,
) -> float:
    params = _regime_scoring_params()
    confidence = params.get("confidence", {})
    readiness = (
        _param_float(confidence, "breadth_ready_weight", 0.34) if breadth_ready else 0.0
    ) + (
        _param_float(confidence, "emotion_ready_weight", 0.24) if emotion_ready else 0.0
    )
    score_component = _normalize_with_params(params, "regime_score", regime_score) * _param_float(confidence, "score_weight", 0.34)
    pressure_penalty = _clamp(distribution_pressure / 100.0, 0.0, 1.0) * _param_float(confidence, "pressure_penalty_weight", 0.16)
    return round(_clamp(_param_float(confidence, "base", 0.24) + readiness + score_component - pressure_penalty), 4)


def market_breadth_sequence_key(recent_hot_sequences: list[list[str]]) -> str:
    flattened = ["|".join(sequence[:3]) for sequence in recent_hot_sequences[:3] if sequence]
    return ">".join(flattened) or "default"


def _average(*values: float) -> float:
    return sum(values) / max(len(values), 1)


def _normalize(value: float, low: float, high: float) -> float:
    if high <= low:
        return 0.0
    clipped = min(max(value, low), high)
    return (clipped - low) / (high - low) * 100.0


def _normalize_with_params(params: dict, key: str, value: float) -> float:
    bounds = params.get("normalizers", {}).get(key)
    if isinstance(bounds, (list, tuple)) and len(bounds) >= 2:
        return _normalize(float(value), float(bounds[0]), float(bounds[1]))
    return _normalize(float(value), 0.0, 1.0)


def _regime_scoring_params() -> dict:
    from app.services.quant.runtime_parameters import get_market_regime_scoring

    values = get_market_regime_scoring()
    return values if isinstance(values, dict) else {}


def _param_float(values: dict, key: str, default: float) -> float:
    try:
        return float(values.get(key, default))
    except (TypeError, ValueError):
        return float(default)


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _clamp_score(value: float) -> float:
    return max(0.0, min(100.0, value))
