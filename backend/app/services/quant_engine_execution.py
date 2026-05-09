from __future__ import annotations

from typing import Any

from app.models.schemas import MicrostructureSnapshot, QuoteSnapshot, SectorSnapshot
from app.services.distribution_signals import DistributionSnapshot
from app.services.market.regime import MarketRegimeSnapshot
from app.services.quant_engine_common import config_float
from app.services.quant_engine_market import market_profit_threshold_shift
from app.services.quant_engine_execution_params import (
    asset_bucket as _asset_bucket,
    bucket_float as _bucket_float,
    dict_param as _dict_param,
    direction_gate_params as _direction_gate_params,
    execution_cost_params as _execution_cost_params,
    list_param as _list_param,
    liquidity_bonus as _liquidity_bonus,
    negative_buyback_anchor as _negative_buyback_anchor,
    param_float as _param_float,
    range_bonus as _range_bonus,
    tier_bonus as _tier_bonus,
)
from app.services.quant_engine_trade_levels import (
    attach_trade_costs,
    min_risk_reward_ratio,
    negative_buyback_allowed,
    negative_buyback_trigger,
    net_profit_floor_pct_for_quote,
    position_pct,
    risk_reward_metrics,
    trade_levels,
)
from app.services.quant_engine_positive_gates import (
    positive_direction_gate,
    positive_light_direction_gate,
    positive_prepare_gate,
)


def estimate_slippage_bps(
    quote: QuoteSnapshot,
    tradability_score: float,
    risk_level: str,
    risk_config: dict[str, Any],
) -> float:
    params = _execution_cost_params()
    baseline = (
        config_float(risk_config, "strategy_slippage_etf_bps", 4.0)
        if quote.instrument_type == "etf"
        else config_float(risk_config, "strategy_slippage_stock_bps", 7.0)
    )
    liquidity_penalty = max(0.0, _param_float(params, "slippage_liquidity_score_floor", 60.0) - tradability_score) * _param_float(params, "slippage_liquidity_penalty_weight", 0.18)
    if risk_level == "medium":
        baseline += _param_float(params, "slippage_medium_risk_add_bps", 1.5)
    elif risk_level == "high":
        baseline += _param_float(params, "slippage_high_risk_add_bps", 3.5)
    return round(max(_param_float(params, "slippage_min_bps", 2.0), min(_param_float(params, "slippage_max_bps", 25.0), baseline + liquidity_penalty)), 2)


def min_profit_pct_for_quote(
    quote: QuoteSnapshot,
    config: dict[str, Any],
    tradability_score: float,
    amplitude: float,
    market_regime: MarketRegimeSnapshot | None = None,
) -> float:
    params = _execution_cost_params()
    legacy_default = config_float(config, "strategy_min_profit_pct", 3.0)
    tradability_bonus = _tier_bonus(
        params.get("tradability_bonus_tiers"),
        value=tradability_score,
        value_key="min_score",
        bonus_key="bonus_pct",
    )
    amplitude_bonus = _range_bonus(
        params.get("amplitude_bonus_tiers"),
        value=amplitude,
        min_key="min_pct",
        max_key="max_pct",
        bonus_key="bonus_pct",
    )
    liquidity_bonus = 0.0
    if quote.instrument_type == "etf":
        base = config_float(config, "strategy_min_profit_etf_pct", max(1.5, legacy_default))
        liquidity_bonus = _liquidity_bonus(params, quote.amount, "etf_bonus_pct")
        adjusted = base - tradability_bonus - amplitude_bonus - liquidity_bonus + market_profit_threshold_shift(
            market_regime,
            instrument_type=quote.instrument_type,
        )
        return round(max(_param_float(params, "min_profit_floor_etf_pct", 0.6), adjusted), 2)
    base = config_float(config, "strategy_min_profit_stock_pct", legacy_default)
    if quote.amount >= _param_float(params, "stock_amount_bonus_threshold", 150_000_000.0):
        tradability_bonus += _param_float(params, "stock_amount_bonus_pct", 0.25)
    liquidity_bonus = _liquidity_bonus(params, quote.amount, "stock_bonus_pct")
    adjusted = base - tradability_bonus - amplitude_bonus - liquidity_bonus + market_profit_threshold_shift(
        market_regime,
        instrument_type=quote.instrument_type,
    )
    return round(max(_param_float(params, "min_profit_floor_stock_pct", 1.5), adjusted), 2)


def light_profit_pct_for_quote(
    quote: QuoteSnapshot,
    sector: SectorSnapshot,
    market_regime: MarketRegimeSnapshot | None = None,
) -> float:
    """Lower gross edge used only for small-size light execution signals."""

    asset_bucket = _asset_bucket(quote, sector)
    params = _execution_cost_params()
    base_map = _dict_param(params, "light_profit_base_pct")
    floor_map = _dict_param(params, "light_profit_floor_pct")
    positive_discount_map = _dict_param(params, "light_profit_positive_state_discount_pct")
    weak_add_map = _dict_param(params, "light_profit_weak_state_add_pct")
    base = float(base_map.get(asset_bucket, base_map.get("thematic_stock", 1.12)) or 1.12)
    state = market_regime.state if market_regime is not None else "low_volume_wait"
    if state in {"broad_rally", "repair"}:
        base -= float(positive_discount_map.get(asset_bucket, positive_discount_map.get("thematic_stock", 0.05)) or 0.05)
    elif state in {"fast_rotation", "high_flyer_retreat", "risk_release"}:
        base += float(weak_add_map.get(asset_bucket, weak_add_map.get("thematic_stock", 0.15)) or 0.15)
    floor = float(floor_map.get(asset_bucket, floor_map.get("thematic_stock", 0.72)) or 0.72)
    return round(max(floor, base), 2)


def negative_direction_gate(
    quote: QuoteSnapshot,
    ma5: float,
    rsi14: float,
    macd_hist: float,
    vwap_value: float,
    amplitude: float,
    sector: SectorSnapshot,
    microstructure: MicrostructureSnapshot,
    distribution: DistributionSnapshot,
    market_regime: MarketRegimeSnapshot | None = None,
    intraday_structure: str = "",
) -> tuple[bool, str]:
    state = market_regime.state if market_regime is not None else "low_volume_wait"
    asset_bucket = _asset_bucket(quote, sector)
    distribution_bias = (
        distribution.false_breakout_flag
        or distribution.stall_after_volume_flag
        or distribution.intraday_reversal_flag
        or distribution.distribution_risk_score >= 5.5
    )
    if intraday_structure not in {"overheat_exhaustion", "volume_stall", "false_breakout"}:
        return False, "先卖后接回只做冲高变弱：需要冲高乏力、放量不涨或假突破结构，横盘小波动不先卖。"
    amplitude_floor = 1.8
    if asset_bucket == "etf" and state == "weight_support":
        amplitude_floor = 1.4
    elif asset_bucket == "etf" and state == "weight_support_active":
        amplitude_floor = 1.55
    elif asset_bucket == "weight_stock" and state == "weight_support":
        amplitude_floor = 1.6
    elif asset_bucket == "weight_stock" and state == "weight_support_active":
        amplitude_floor = 1.75
    elif asset_bucket == "thematic_stock" and state == "weight_support_active":
        amplitude_floor = 1.95
    elif asset_bucket == "thematic_stock" and state == "fast_rotation":
        amplitude_floor = 2.12
    elif asset_bucket == "etf" and state in {"high_flyer_retreat", "risk_release"}:
        amplitude_floor = 1.72
    elif state in {"high_flyer_retreat", "risk_release"}:
        amplitude_floor = 2.0 if asset_bucket == "weight_stock" else 2.25
    if distribution.false_breakout_flag:
        amplitude_floor = max(1.25, amplitude_floor - (0.45 if asset_bucket == "etf" else 0.35))
    elif distribution.intraday_reversal_flag:
        amplitude_floor = max(1.35, amplitude_floor - 0.2)
    elif distribution.stall_after_volume_flag:
        amplitude_floor = max(1.45, amplitude_floor - 0.12)
    if amplitude < amplitude_floor:
        return False, "当天波动太小，冲高后回落接回的空间不够。"
    room_allowed, room_reason = _negative_buyback_room_allowed(
        quote=quote,
        ma5=ma5,
        vwap_value=vwap_value,
        asset_bucket=asset_bucket,
        distribution_bias=distribution_bias,
    )
    if not room_allowed:
        return False, room_reason
    relative_price_floor = 1.001 if not distribution_bias else 0.998
    relative_vwap_floor = 1.002 if not distribution_bias else 0.998
    rsi_floor = 60 if quote.instrument_type == "etf" else 62
    if distribution_bias:
        rsi_floor -= 3
    if quote.last_price < ma5 * relative_price_floor and quote.last_price < vwap_value * relative_vwap_floor and rsi14 < rsi_floor:
        return False, "价格并未明显强于短线均价，不适合先卖。"
    if rsi14 < (56 if not distribution_bias else 53) and macd_hist >= 0.02:
        return False, "短线还没有明显过热，先卖优势不足。"
    sell_pressure_floor = 48
    if asset_bucket == "etf" and state == "weight_support":
        sell_pressure_floor = 46
    elif asset_bucket == "etf" and state == "weight_support_active":
        sell_pressure_floor = 47
    elif asset_bucket == "weight_stock" and state in {"weight_support", "weight_support_active"}:
        sell_pressure_floor = 46
    elif asset_bucket == "thematic_stock" and state in {"weight_support", "high_flyer_retreat", "risk_release"}:
        sell_pressure_floor = 50
    elif asset_bucket == "thematic_stock" and state == "fast_rotation":
        sell_pressure_floor = 51
    if distribution.false_breakout_flag:
        sell_pressure_floor -= 4
    elif distribution.intraday_reversal_flag:
        sell_pressure_floor -= 3
    elif distribution.stall_after_volume_flag:
        sell_pressure_floor -= 2
    weak_sell_pressure = microstructure.available and microstructure.sell_pressure < sell_pressure_floor
    rsi_not_hot = rsi14 < (60 if not distribution_bias else 57)
    amplitude_too_small = amplitude < (2.6 if not distribution_bias else 2.3)
    if weak_sell_pressure and rsi_not_hot and amplitude_too_small:
        return False, "卖盘压力不明显，先卖后接回成功率不足。"
    return True, ""


def negative_light_direction_gate(
    quote: QuoteSnapshot,
    ma5: float,
    rsi14: float,
    macd_hist: float,
    vwap_value: float,
    amplitude: float,
    sector: SectorSnapshot,
    microstructure: MicrostructureSnapshot,
    distribution: DistributionSnapshot,
    market_regime: MarketRegimeSnapshot | None = None,
    intraday_structure: str = "",
) -> tuple[bool, str]:
    state = market_regime.state if market_regime is not None else "low_volume_wait"
    asset_bucket = _asset_bucket(quote, sector)
    distribution_bias = (
        distribution.false_breakout_flag
        or distribution.stall_after_volume_flag
        or distribution.intraday_reversal_flag
        or distribution.distribution_risk_score >= 5.2
    )
    structure_ok = intraday_structure in {"overheat_exhaustion", "volume_stall", "false_breakout"}
    soft_structure_ok = intraday_structure in {"balanced_intraday", "range_contraction"} and distribution_bias
    if not structure_ok and not soft_structure_ok:
        return False, "小仓先卖也需要冲高变弱，或有明确出货迹象。"
    amplitude_floor = {"etf": 1.25, "weight_stock": 1.45}.get(asset_bucket, 1.72)
    if state in {"fast_rotation", "high_flyer_retreat", "risk_release"}:
        amplitude_floor -= 0.12
    if amplitude < amplitude_floor:
        return False, "当天波动仍不足，小仓先卖后的价差不够。"
    room_allowed, room_reason = _negative_buyback_room_allowed(
        quote=quote,
        ma5=ma5,
        vwap_value=vwap_value,
        asset_bucket=asset_bucket,
        distribution_bias=True,
    )
    if not room_allowed:
        return False, room_reason
    near_high = quote.high_price > 0 and quote.last_price >= quote.high_price * 0.982
    if not near_high:
        return False, "小仓先卖也必须在分时高位附近。"
    heat_ok = rsi14 >= (54 if asset_bucket == "etf" else 57) or macd_hist < -0.01 or distribution_bias
    pressure_ok = not microstructure.available or microstructure.sell_pressure >= (44 if asset_bucket == "etf" else 48)
    if not heat_ok or not pressure_ok:
        return False, "过热或卖盘证据不足，小仓先卖不放宽。"
    return True, "冲高区域已有出货或变弱倾向，且回落接回空间够，只允许小仓先卖后接回。"


def negative_prepare_gate(
    quote: QuoteSnapshot,
    ma5: float,
    vwap_value: float,
    amplitude: float,
    sector: SectorSnapshot,
    microstructure: MicrostructureSnapshot,
    distribution: DistributionSnapshot,
    market_regime: MarketRegimeSnapshot | None = None,
    intraday_structure: str = "",
) -> tuple[bool, str]:
    asset_bucket = _asset_bucket(quote, sector)
    distribution_bias = (
        distribution.false_breakout_flag
        or distribution.stall_after_volume_flag
        or distribution.intraday_reversal_flag
        or distribution.distribution_risk_score >= 4.8
    )
    near_high = quote.high_price > 0 and quote.last_price >= quote.high_price * 0.985
    anchor = _negative_buyback_anchor(ma5=ma5, vwap_value=vwap_value)
    room_pct = (quote.last_price - anchor) / max(quote.last_price, 0.01) * 100 if anchor > 0 else 0.0
    min_room = {"etf": 0.28, "weight_stock": 0.45}.get(asset_bucket, 0.62)
    if near_high and room_pct >= min_room and (distribution_bias or microstructure.sell_pressure >= 50 or amplitude >= 1.6):
        return True, "价格接近当天高位且回落接回空间初步够，等冲高变弱或放量不涨确认后再先卖后接回。"
    if intraday_structure in {"volume_stall", "overheat_exhaustion"} and room_pct >= min_room * 0.8:
        return True, "已有冲高乏力迹象，但回落接回空间还需扩大，先列为先卖后接回预备信号。"
    return False, "先卖后接回条件尚未接近。"


def _negative_buyback_room_allowed(
    *,
    quote: QuoteSnapshot,
    ma5: float,
    vwap_value: float,
    asset_bucket: str,
    distribution_bias: bool,
) -> tuple[bool, str]:
    if quote.last_price <= 0 or ma5 <= 0 or vwap_value <= 0:
        return False, "缺少有效的分时均价线或5日线参考位，不能先卖。"
    params = _direction_gate_params("negative_buyback_room")
    buyback_anchor = _negative_buyback_anchor(ma5=ma5, vwap_value=vwap_value)
    distance_to_reference_pct = (quote.last_price - buyback_anchor) / max(quote.last_price, 0.01) * 100
    min_distance = _bucket_float(_dict_param(params, "min_distance_pct"), asset_bucket, 0.75)
    if distribution_bias:
        min_distance *= _param_float(params, "distribution_bias_multiplier", 0.75)
    if distance_to_reference_pct < min_distance:
        return False, "卖出后回落接回空间不足，当前价距离分时均价线或5日线太近。"
    near_multiplier = _param_float(
        params,
        "near_high_distribution_multiplier" if distribution_bias else "near_high_multiplier",
        0.982 if distribution_bias else 0.988,
    )
    near_intraday_high = quote.high_price > 0 and quote.last_price >= quote.high_price * near_multiplier
    if not near_intraday_high:
        return False, "需要在分时高位附近处理，当前位置不是冲高变弱区。"
    estimated_buyback = buyback_anchor * _param_float(params, "estimated_buyback_multiplier", 0.998)
    round_trip_cost = _bucket_float(_dict_param(params, "round_trip_cost_pct"), asset_bucket, 0.28)
    min_net_room = _bucket_float(_dict_param(params, "min_net_room_pct"), asset_bucket, 0.55)
    net_room = (quote.last_price - estimated_buyback) / max(quote.last_price, 0.01) * 100 - round_trip_cost
    if net_room < min_net_room:
        return False, "扣除买卖费用和成交偏差后，回落接回的实际空间不足。"
    return True, ""
