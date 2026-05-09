from __future__ import annotations

import pandas as pd

from app.services.market.emotion import MarketEmotionSnapshot
from app.services.market.regime_types import (
    DEFENSIVE_KEYWORDS,
    STATE_CONFIG,
    MarketBreadthSnapshot,
    MarketRegimeSnapshot,
)
from app.services.market.regime_score_builder import (
    _clamp,
    build_state_scores,
    composite_distribution_pressure,
    mainline_lifecycle,
    regime_confidence,
    retreat_pressure_score,
    select_state,
)
from app.services.market.regime_snapshot_utils import (
    clone_snapshot_with_state,
    market_regime_text,
    normalize_board_frame,
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
    retreat_pressure = retreat_pressure_score(
        emotion_ready=emotion.emotion_ready,
        high_flyer_retreat_ratio=emotion.high_flyer_retreat_ratio,
        broken_board_ratio=emotion.broken_board_ratio,
        limit_down_value=float(limit_down_count or 0),
        promotion_break_pressure=emotion.promotion_break_pressure,
        high_flyer_gap_speed=emotion.high_flyer_gap_speed,
    )
    distribution_pressure = composite_distribution_pressure(
        emotion_ready=emotion.emotion_ready,
        retreat_pressure=retreat_pressure,
        high_flyer_gap_speed=emotion.high_flyer_gap_speed,
        promotion_break_pressure=emotion.promotion_break_pressure,
        stock_up_ratio=breadth.stock_up_ratio,
    )
    mainline_state, mainline_text = mainline_lifecycle(
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
    state, regime_score = select_state(state_scores)
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
        regime_confidence=regime_confidence(
            regime_score=regime_score,
            breadth_ready=breadth.breadth_ready,
            emotion_ready=emotion.emotion_ready,
            distribution_pressure=distribution_pressure,
        ),
        state_persistence_days=1,
        transition_risk=0.0,
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

def market_breadth_sequence_key(recent_hot_sequences: list[list[str]]) -> str:
    flattened = ["|".join(sequence[:3]) for sequence in recent_hot_sequences[:3] if sequence]
    return ">".join(flattened) or "default"
