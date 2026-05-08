from __future__ import annotations

from app.services.market.regime import MarketRegimeSnapshot
from app.services.quant.runtime_parameters import get_position_t_decision


def ensure_market_regime(market_regime: MarketRegimeSnapshot | None) -> MarketRegimeSnapshot:
    return market_regime or _default_market_regime()


def market_threshold_shift(market_regime: MarketRegimeSnapshot | None) -> tuple[float, float]:
    snapshot = ensure_market_regime(market_regime)
    severity = _state_strength(snapshot)
    params = _market_params()
    base_weight = _float_param(params, "market_shift_base_weight")
    strength_weight = _float_param(params, "market_shift_strength_weight")
    return (
        round(snapshot.positive_threshold_shift * (base_weight + severity * strength_weight), 2),
        round(snapshot.negative_threshold_shift * (base_weight + severity * strength_weight), 2),
    )


def market_position_multiplier(
    market_regime: MarketRegimeSnapshot | None,
    instrument_type: str = "stock",
) -> float:
    snapshot = ensure_market_regime(market_regime)
    severity = _state_strength(snapshot)
    params = _market_params()
    base = snapshot.position_multiplier
    if base >= 1.0:
        multiplier = 1.0 + (base - 1.0) * severity
    else:
        multiplier = 1.0 - (1.0 - base) * max(severity, _float_param(params, "market_shift_strength_weight"))
    if instrument_type == "etf" and snapshot.state in {"weight_support", "weight_support_active", "risk_release", "high_flyer_retreat"}:
        multiplier += _float_param(params, "market_etf_defense_bonus")
    return round(
        max(_float_param(params, "market_position_min_multiplier"), min(_float_param(params, "market_position_max_multiplier"), multiplier)),
        4,
    )


def market_profit_threshold_shift(
    market_regime: MarketRegimeSnapshot | None,
    instrument_type: str = "stock",
) -> float:
    snapshot = ensure_market_regime(market_regime)
    severity = _state_strength(snapshot)
    params = _market_params()
    shift = snapshot.t_threshold_shift * (_float_param(params, "market_shift_base_weight") + severity * _float_param(params, "market_shift_strength_weight"))
    if instrument_type == "etf" and snapshot.state == "weight_support":
        shift *= _float_param(params, "market_etf_weight_support_profit_multiplier")
    elif instrument_type == "etf" and snapshot.state == "weight_support_active":
        shift *= _float_param(params, "market_etf_weight_support_active_profit_multiplier")
    elif instrument_type == "etf" and snapshot.state == "risk_release":
        shift *= _float_param(params, "market_etf_risk_release_profit_multiplier")
    return round(shift, 4)


def market_risk_reward_shift(
    market_regime: MarketRegimeSnapshot | None,
    instrument_type: str = "stock",
) -> float:
    snapshot = ensure_market_regime(market_regime)
    params = _market_params()
    shifts = params.get("market_min_risk_reward_shift", {})
    state_shift = float(shifts.get(snapshot.state, 0.0)) if isinstance(shifts, dict) else 0.0
    shift = state_shift * (_float_param(params, "market_shift_base_weight") + _state_strength(snapshot) * _float_param(params, "market_shift_strength_weight"))
    if instrument_type == "etf" and snapshot.state in {"weight_support", "weight_support_active", "risk_release"}:
        shift *= _float_param(params, "market_etf_defense_risk_reward_multiplier")
    return round(shift, 4)


def market_state_text(market_regime: MarketRegimeSnapshot | None) -> str:
    snapshot = ensure_market_regime(market_regime)
    return snapshot.label


def market_state_description(market_regime: MarketRegimeSnapshot | None) -> str:
    snapshot = ensure_market_regime(market_regime)
    return snapshot.description


def _state_strength(snapshot: MarketRegimeSnapshot) -> float:
    return max(0.0, min(snapshot.state_strength or 0.0, 1.0))


def _default_market_regime() -> MarketRegimeSnapshot:
    params = _market_params()
    return MarketRegimeSnapshot(
        state=str(params.get("market_default_state") or "low_volume_wait"),
        label="缩量无主线",
        description="环境数据不足时按中性偏防守处理，优先等待确认。",
        ranking_bonus=_float_param(params, "market_default_ranking_bonus"),
        position_multiplier=_float_param(params, "market_default_position_multiplier"),
        buy_signal_penalty=_float_param(params, "market_default_buy_signal_penalty"),
        t_threshold_shift=_float_param(params, "market_default_t_threshold_shift"),
        positive_threshold_shift=_float_param(params, "market_default_positive_threshold_shift"),
        negative_threshold_shift=_float_param(params, "market_default_negative_threshold_shift"),
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


def _market_params() -> dict:
    return get_position_t_decision()


def _float_param(params: dict, key: str) -> float:
    try:
        return float(params[key])
    except (KeyError, TypeError, ValueError):
        from app.services.low_buy.strategy_parameter_defaults import POSITION_T_DECISION_DEFAULTS

        return float(POSITION_T_DECISION_DEFAULTS[key])
