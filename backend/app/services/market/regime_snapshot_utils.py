from __future__ import annotations

import pandas as pd

from app.services.market.regime_types import STATE_CONFIG, MarketRegimeSnapshot


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


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))
