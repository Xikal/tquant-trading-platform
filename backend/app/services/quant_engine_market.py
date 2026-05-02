from __future__ import annotations

from app.services.market.regime import MarketRegimeSnapshot


_DEFAULT_MARKET_REGIME = MarketRegimeSnapshot(
    state="low_volume_wait",
    label="缩量观望",
    description="环境数据不足时按中性偏防守处理，优先等待确认。",
    ranking_bonus=-2.0,
    position_multiplier=0.75,
    buy_signal_penalty=1.5,
    t_threshold_shift=0.12,
    positive_threshold_shift=2.0,
    negative_threshold_shift=2.0,
    hot_industries=[],
    hot_industry_source="",
    hot_industry_source_text="",
    limit_down_count=None,
    breadth_ready=False,
    emotion_ready=False,
    positive_industry_ratio=0.0,
    top3_avg_change=0.0,
    median_change=0.0,
    defensive_lead=False,
    stock_up_ratio=0.0,
    stock_median_change=0.0,
    largecap_change=0.0,
    smallcap_change=0.0,
    style_divergence=0.0,
    hot_turnover=0.0,
    hot_overlap_ratio=0.0,
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
    distribution_pressure=0.0,
    mainline_lifecycle_state="unknown",
    mainline_lifecycle_text="主线阶段：热点归因不足",
    state_strength=0.0,
    regime_score=0.0,
)

_MIN_RISK_REWARD_SHIFT = {
    "broad_rally": -0.05,
    "repair": -0.02,
    "low_volume_wait": 0.03,
    "fast_rotation": 0.05,
    "weight_support": 0.08,
    "weight_support_active": 0.03,
    "high_flyer_retreat": 0.10,
    "risk_release": 0.15,
}


def ensure_market_regime(market_regime: MarketRegimeSnapshot | None) -> MarketRegimeSnapshot:
    return market_regime or _DEFAULT_MARKET_REGIME


def market_threshold_shift(market_regime: MarketRegimeSnapshot | None) -> tuple[float, float]:
    snapshot = ensure_market_regime(market_regime)
    severity = _state_strength(snapshot)
    return (
        round(snapshot.positive_threshold_shift * (0.55 + severity * 0.45), 2),
        round(snapshot.negative_threshold_shift * (0.55 + severity * 0.45), 2),
    )


def market_position_multiplier(
    market_regime: MarketRegimeSnapshot | None,
    instrument_type: str = "stock",
) -> float:
    snapshot = ensure_market_regime(market_regime)
    severity = _state_strength(snapshot)
    base = snapshot.position_multiplier
    if base >= 1.0:
        multiplier = 1.0 + (base - 1.0) * severity
    else:
        multiplier = 1.0 - (1.0 - base) * max(severity, 0.45)
    if instrument_type == "etf" and snapshot.state in {"weight_support", "weight_support_active", "risk_release", "high_flyer_retreat"}:
        multiplier += 0.12
    return round(max(0.35, min(1.2, multiplier)), 4)


def market_profit_threshold_shift(
    market_regime: MarketRegimeSnapshot | None,
    instrument_type: str = "stock",
) -> float:
    snapshot = ensure_market_regime(market_regime)
    severity = _state_strength(snapshot)
    shift = snapshot.t_threshold_shift * (0.55 + severity * 0.45)
    if instrument_type == "etf" and snapshot.state == "weight_support":
        shift *= 0.45
    elif instrument_type == "etf" and snapshot.state == "weight_support_active":
        shift *= 0.7
    elif instrument_type == "etf" and snapshot.state == "risk_release":
        shift *= 0.65
    return round(shift, 4)


def market_risk_reward_shift(
    market_regime: MarketRegimeSnapshot | None,
    instrument_type: str = "stock",
) -> float:
    snapshot = ensure_market_regime(market_regime)
    shift = _MIN_RISK_REWARD_SHIFT.get(snapshot.state, 0.0) * (0.55 + _state_strength(snapshot) * 0.45)
    if instrument_type == "etf" and snapshot.state in {"weight_support", "weight_support_active", "risk_release"}:
        shift *= 0.6
    return round(shift, 4)


def market_state_text(market_regime: MarketRegimeSnapshot | None) -> str:
    snapshot = ensure_market_regime(market_regime)
    return snapshot.label


def market_state_description(market_regime: MarketRegimeSnapshot | None) -> str:
    snapshot = ensure_market_regime(market_regime)
    return snapshot.description


def _state_strength(snapshot: MarketRegimeSnapshot) -> float:
    return max(0.0, min(snapshot.state_strength or 0.0, 1.0))
