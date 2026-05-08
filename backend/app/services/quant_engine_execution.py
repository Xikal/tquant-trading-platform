from __future__ import annotations

from typing import Any

from app.core.database import SessionLocal
from app.models.schemas import MicrostructureSnapshot, QuoteSnapshot, SectorSnapshot
from app.services.distribution_signals import DistributionSnapshot
from app.services.market.regime import MarketRegimeSnapshot
from app.services.quant_engine_common import config_float
from app.services.quant_engine_models import TradeCostEstimate
from app.services.quant_engine_market import (
    market_position_multiplier,
    market_profit_threshold_shift,
    market_risk_reward_shift,
)
from app.services.quant.runtime_parameters import get_position_t_decision
from app.services.shared.trading_costs import estimate_round_trip_cost
from app.services.shared.feature_flags import feature_enabled
from app.services.shared.trading_elasticity import get_trading_elasticity

_WEIGHT_SECTOR_KEYWORDS = (
    "银行",
    "保险",
    "石油",
    "煤炭",
    "运营商",
    "电力",
    "铁路公路",
    "高速公路",
)


def _asset_bucket(quote: QuoteSnapshot, sector: SectorSnapshot | None = None) -> str:
    if quote.instrument_type == "etf":
        return "etf"
    sector_name = (sector.sector_name if sector is not None else "") or ""
    if any(keyword in sector_name for keyword in _WEIGHT_SECTOR_KEYWORDS):
        return "weight_stock"
    return "thematic_stock"


def _decision_params() -> dict[str, Any]:
    try:
        values = get_position_t_decision()
    except Exception:
        values = {}
    return values if isinstance(values, dict) else {}


def _execution_cost_params() -> dict[str, Any]:
    values = _decision_params().get("execution_costs", {})
    return values if isinstance(values, dict) else {}


def _direction_gate_params(name: str) -> dict[str, Any]:
    values = _decision_params().get("direction_gates", {})
    if not isinstance(values, dict):
        return {}
    section = values.get(name, {})
    return section if isinstance(section, dict) else {}


def _param_float(params: dict[str, Any], key: str, default: float) -> float:
    try:
        return float(params.get(key, default))
    except (TypeError, ValueError):
        return default


def _dict_param(params: dict[str, Any], key: str) -> dict[str, Any]:
    value = params.get(key, {})
    return value if isinstance(value, dict) else {}


def _list_param(params: dict[str, Any], key: str) -> list[str]:
    value = params.get(key, [])
    return [str(item) for item in value] if isinstance(value, list) else []


def _bucket_state_params(params: dict[str, Any], asset_bucket: str, state: str) -> dict[str, float]:
    result = dict(_dict_param(params, "default"))
    overrides = _dict_param(params, "state_overrides")
    specific = overrides.get(f"{asset_bucket}.{state}", {})
    if isinstance(specific, dict):
        result.update(specific)
    return result


def _bucket_float(mapping: dict[str, Any], asset_bucket: str, default: float) -> float:
    try:
        return float(mapping.get(asset_bucket, mapping.get("thematic_stock", default)))
    except (TypeError, ValueError):
        return default


def _tier_bonus(tiers: Any, *, value: float, value_key: str, bonus_key: str) -> float:
    if not isinstance(tiers, list):
        return 0.0
    valid_tiers = [item for item in tiers if isinstance(item, dict)]
    valid_tiers.sort(key=lambda item: _param_float(item, value_key, 0.0), reverse=True)
    for item in valid_tiers:
        if value >= _param_float(item, value_key, 0.0):
            return _param_float(item, bonus_key, 0.0)
    return 0.0


def _range_bonus(tiers: Any, *, value: float, min_key: str, max_key: str, bonus_key: str) -> float:
    if not isinstance(tiers, list):
        return 0.0
    for item in tiers:
        if not isinstance(item, dict):
            continue
        lower = _param_float(item, min_key, 0.0)
        upper = _param_float(item, max_key, 0.0)
        if lower < value <= upper:
            return _param_float(item, bonus_key, 0.0)
    return 0.0


def _liquidity_bonus(params: dict[str, Any], amount: float, bonus_key: str) -> float:
    tiers = params.get("liquidity_bonus_tiers", [])
    if not isinstance(tiers, list):
        return 0.0
    valid_tiers = [item for item in tiers if isinstance(item, dict)]
    valid_tiers.sort(key=lambda item: _param_float(item, "min_amount", 0.0), reverse=True)
    for item in valid_tiers:
        if amount >= _param_float(item, "min_amount", 0.0):
            return _param_float(item, bonus_key, 0.0)
    return 0.0


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


def net_profit_floor_pct_for_quote(
    quote: QuoteSnapshot,
    action: str,
    sector: SectorSnapshot | None = None,
) -> float:
    """Minimum fee-adjusted edge required before a signal is executable."""

    asset_bucket = _asset_bucket(quote, sector)
    params = _execution_cost_params()
    floor_map = _dict_param(params, "net_profit_floor_pct")
    bucket_values = floor_map.get(asset_bucket) if isinstance(floor_map.get(asset_bucket), dict) else {}
    if not isinstance(bucket_values, dict):
        bucket_values = {}
    default_bucket = {"etf": 0.25, "weight_stock": 0.45 if action == "negative_t" else 0.50}.get(asset_bucket, 0.80 if action == "negative_t" else 0.90)
    try:
        return float(bucket_values.get(action, default_bucket))
    except (TypeError, ValueError):
        return float(default_bucket)


def positive_direction_gate(
    quote: QuoteSnapshot,
    ma5: float,
    ma20: float,
    slope10: float,
    vwap_value: float,
    sector: SectorSnapshot,
    microstructure: MicrostructureSnapshot,
    distribution: DistributionSnapshot,
    market_regime: MarketRegimeSnapshot | None = None,
    intraday_structure: str = "",
) -> tuple[bool, str]:
    asset_bucket = _asset_bucket(quote, sector)
    state = market_regime.state if market_regime is not None else "low_volume_wait"
    params = _direction_gate_params("positive")
    gate = _bucket_state_params(params, asset_bucket, state)
    price_extension_limit = _param_float(gate, "price_extension_limit", 1.035)
    weak_vwap_limit = _param_float(gate, "weak_vwap_limit", 0.992)
    slope_floor = _param_float(gate, "slope_floor", -0.26)
    weak_sector_floor = _param_float(gate, "weak_sector_floor", 44.0)
    weak_buy_pressure_floor = _param_float(gate, "weak_buy_pressure_floor", 44.0)
    distribution_reason = _positive_distribution_block(
        asset_bucket=asset_bucket,
        state=state,
        distribution=distribution,
    )
    if distribution_reason:
        return False, distribution_reason
    if _thematic_positive_state_block(
        asset_bucket=asset_bucket,
        state=state,
        sector=sector,
        microstructure=microstructure,
    ):
        return False, "题材股处在退潮/快速轮动环境，必须等板块和买盘同时转强后再考虑先买后卖。"
    if intraday_structure != str(params.get("required_structure") or "pullback_acceptance"):
        return False, "先买后卖只做回落后有人接盘：必须先靠近分时均价线或5日线，再重新站回分时均价线，且短线低点抬高、回落时成交量缩小。"
    if quote.last_price < vwap_value * _param_float(params, "reclaim_vwap_multiplier", 1.001):
        return False, "需要重新站回分时均价线后再考虑先买后卖。"
    if quote.last_price > ma5 * price_extension_limit:
        return False, "价格离5日线已经偏远，不建议追着买。"
    if quote.last_price < ma20 * _param_float(params, "ma20_floor_multiplier", 0.992):
        return False, "价格已经跌到20日线下方，当前不适合先买后卖。"
    if slope10 < slope_floor:
        return False, "短线趋势转弱，先买后卖的成功条件不足。"
    weak_sector = sector.alignment_score < weak_sector_floor
    if asset_bucket == "weight_stock":
        weak_sector = weak_sector and state not in set(
            _list_param(params, "weight_stock_support_states") or ["weight_support", "weight_support_active"]
        )
    weak_buy_pressure = microstructure.available and microstructure.buy_pressure < weak_buy_pressure_floor
    weak_vwap = quote.last_price < vwap_value * weak_vwap_limit
    if weak_sector and weak_buy_pressure:
        return False, "板块联动和买盘承接同时偏弱，先买后卖成功率不足。"
    if weak_vwap and slope10 < _param_float(params, "weak_vwap_slope_floor", -0.12):
        return False, "价格仍弱于分时均价线，先等回到均价附近再考虑先买后卖。"
    return True, ""


def positive_light_direction_gate(
    quote: QuoteSnapshot,
    ma5: float,
    ma20: float,
    slope10: float,
    vwap_value: float,
    sector: SectorSnapshot,
    microstructure: MicrostructureSnapshot,
    distribution: DistributionSnapshot,
    market_regime: MarketRegimeSnapshot | None = None,
    intraday_structure: str = "",
) -> tuple[bool, str]:
    asset_bucket = _asset_bucket(quote, sector)
    state = market_regime.state if market_regime is not None else "low_volume_wait"
    if asset_bucket == "thematic_stock" and state in {"high_flyer_retreat", "risk_release"}:
        return False, "退潮或风险释放时，题材股不放宽先买后卖条件。"
    if distribution.false_breakout_flag or distribution.distribution_risk_score >= (7.6 if asset_bucket == "etf" else 6.4):
        return False, "出货或假突破风险偏高，不能放宽先买后卖。"
    if intraday_structure not in {"pullback_acceptance", "sharp_drop_repair"}:
        return False, "小仓试做只接受回落有人接盘，或急跌后重新收回分时均价线的结构。"
    if quote.last_price < vwap_value * (0.999 if asset_bucket == "etf" else 1.0):
        return False, "小仓试做也必须至少回到分时均价线附近。"
    if quote.last_price > ma5 * (1.045 if asset_bucket == "etf" else 1.032):
        return False, "价格离5日线过远，小仓也不追。"
    if quote.last_price < ma20 * 0.985:
        return False, "价格弱于20日线，小仓试做的成功率不足。"
    if slope10 < (-0.36 if asset_bucket == "etf" else -0.22):
        return False, "短线斜率仍偏弱，先等承接继续确认。"
    if sector.alignment_score < (42.0 if asset_bucket != "thematic_stock" else 50.0):
        return False, "板块联动不足，小仓试做不放宽。"
    if microstructure.available and microstructure.buy_pressure < (40.0 if asset_bucket == "etf" else 46.0):
        return False, "买盘承接不足，小仓试做也不放宽。"
    return True, "急跌修复或回落接盘已接近成立，只允许小仓先买后卖，并继续看分时均价线是否守住。"


def positive_prepare_gate(
    quote: QuoteSnapshot,
    ma5: float,
    vwap_value: float,
    sector: SectorSnapshot,
    microstructure: MicrostructureSnapshot,
    distribution: DistributionSnapshot,
    market_regime: MarketRegimeSnapshot | None = None,
    intraday_structure: str = "",
) -> tuple[bool, str]:
    asset_bucket = _asset_bucket(quote, sector)
    state = market_regime.state if market_regime is not None else "low_volume_wait"
    if asset_bucket == "thematic_stock" and state in {"high_flyer_retreat", "risk_release"}:
        return False, "市场退潮时，非 ETF 只保留严格确认后的先买后卖信号。"
    if distribution.false_breakout_flag or distribution.distribution_risk_score >= 7.5:
        return False, "出货风险偏高，不提前提示先买后卖。"
    anchor = min(ma5, vwap_value)
    near_anchor = anchor > 0 and quote.low_price <= anchor * 1.006 and quote.last_price >= anchor * 0.996
    structure_near = intraday_structure in {"sharp_drop_repair", "range_contraction", "balanced_intraday"}
    if near_anchor and structure_near:
        return True, "价格已靠近分时均价线或5日线支撑区，等重新站稳分时均价线并低点抬高后再先买后卖。"
    if microstructure.available and microstructure.buy_pressure >= 55 and quote.last_price >= vwap_value * 0.997:
        return True, "买盘承接转强但结构还未完全确认，先列为先买后卖预备信号。"
    return False, "先买后卖条件尚未接近。"


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


def _negative_buyback_anchor(*, ma5: float, vwap_value: float) -> float:
    return min(ma5, vwap_value)


def _positive_distribution_block(
    *,
    asset_bucket: str,
    state: str,
    distribution: DistributionSnapshot,
) -> str:
    params = _direction_gate_params("positive_distribution_block")
    if distribution.false_breakout_flag:
        return "分时出现假突破回落，不适合逆着出货迹象追买。"
    reversal_score = _param_float(
        params,
        "etf_reversal_score" if asset_bucket == "etf" else "stock_reversal_score",
        8.2 if asset_bucket == "etf" else 7.0,
    )
    if distribution.intraday_reversal_flag and distribution.distribution_risk_score >= reversal_score:
        return "分时冲高回落明显，先等卖压释放。"
    weak_stall_context = state in set(
        _list_param(params, "weak_stall_states") or ["fast_rotation", "high_flyer_retreat", "risk_release"]
    )
    if distribution.stall_after_volume_flag and asset_bucket == "thematic_stock" and weak_stall_context:
        return "放量但价格涨不动，且市场环境偏弱，先买后卖成功率不足。"
    distribution_score = _param_float(
        params,
        "etf_distribution_score" if asset_bucket == "etf" else "stock_distribution_score",
        8.8 if asset_bucket == "etf" else 7.8,
    )
    if distribution.distribution_risk_score >= distribution_score:
        return "当前出货风险偏高，应等待更强承接。"
    return ""


def _thematic_positive_state_block(
    *,
    asset_bucket: str,
    state: str,
    sector: SectorSnapshot,
    microstructure: MicrostructureSnapshot,
) -> bool:
    params = _direction_gate_params("thematic_state_block")
    blocked_states = set(_list_param(params, "blocked_states") or ["fast_rotation", "high_flyer_retreat", "risk_release"])
    if asset_bucket != "thematic_stock" or state not in blocked_states:
        return False
    if not microstructure.available:
        return sector.alignment_score < _param_float(params, "sector_floor", 55.0)
    return sector.alignment_score < _param_float(params, "sector_floor", 55.0) or microstructure.buy_pressure < _param_float(
        params, "buy_pressure_floor", 55.0
    )


def position_pct(
    signal_score: float,
    tradability_score: float,
    risk_level_value: str,
    risk_config: dict[str, Any],
    instrument_type: str,
    market_regime: MarketRegimeSnapshot | None = None,
) -> float:
    base = min(signal_score, tradability_score) * 0.55
    if risk_level_value == "high":
        base *= 0.45
    elif risk_level_value == "medium":
        base *= 0.7
    base *= market_position_multiplier(market_regime, instrument_type=instrument_type)
    cap = max(15.0, 100 * (float(risk_config.get("risk_max_single_loss_pct", 1.0)) / 2.5))
    return round(max(0.0, min(base, cap)), 2)


def min_risk_reward_ratio(
    quote: QuoteSnapshot,
    action: str,
    market_regime: MarketRegimeSnapshot | None = None,
) -> float:
    if action == "hold":
        return 0.0
    if quote.instrument_type == "etf":
        base = 1.0 if action == "negative_t" else 1.08
    else:
        base = 1.12 if action == "negative_t" else 1.22
    return round(max(0.8, base + market_risk_reward_shift(market_regime, instrument_type=quote.instrument_type)), 2)


def risk_reward_metrics(
    action: str,
    entry_price: float,
    exit_price: float,
    stop_loss: float,
) -> tuple[float, float]:
    if action == "positive_t":
        reward = max(exit_price - entry_price, 0.0)
        risk = max(entry_price - stop_loss, 0.0)
        expected_loss_pct = risk / max(entry_price, 0.001) * 100
    else:
        reward = max(entry_price - exit_price, 0.0)
        risk = max(stop_loss - entry_price, 0.0)
        expected_loss_pct = risk / max(entry_price, 0.001) * 100
    if risk <= 0:
        return 0.0, 0.0
    return round(reward / risk, 4), round(expected_loss_pct, 4)


def trade_levels(
    action: str,
    quote: QuoteSnapshot,
    vwap_value: float,
    ma5: float,
    atr_value: float,
    slippage_bps: float,
    max_single_loss_pct: float,
) -> tuple[float | None, float | None, float | None, float | None, float]:
    buffer = max(atr_value * 0.45, quote.last_price * 0.0025)
    slippage = quote.last_price * (slippage_bps / 10000)
    max_loss_ratio = max_single_loss_pct / 100
    if action == "positive_t":
        raw_entry = min(quote.last_price, max(vwap_value, quote.last_price - buffer))
        entry = round(raw_entry + slippage, 3)
        exit_price = round(entry + max(buffer * 1.8, quote.last_price * 0.006) - slippage, 3)
        stop_by_buffer = entry - max(buffer * 1.2, quote.last_price * 0.004)
        stop_by_risk = entry * (1 - max_loss_ratio)
        stop_loss = round(max(stop_by_buffer, stop_by_risk), 3)
        if exit_price <= entry:
            return None, None, None, None, 0.0
        take_profit = round(exit_price, 3)
        expected_profit_pct = (exit_price - entry) / max(entry, 0.001) * 100
        return entry, exit_price, stop_loss, take_profit, round(expected_profit_pct, 4)
    if action == "negative_t":
        raw_sell = max(quote.last_price, quote.last_price + buffer * 0.5)
        sell_price = round(raw_sell - slippage, 3)
        buyback_anchor = _negative_buyback_anchor(ma5=ma5, vwap_value=vwap_value)
        raw_buyback = min(buyback_anchor, quote.last_price - max(buffer * 1.6, quote.last_price * 0.005))
        buy_price = round(raw_buyback + slippage, 3)
        stop_by_buffer = sell_price + max(buffer * 1.2, quote.last_price * 0.004)
        stop_by_risk = sell_price * (1 + max_loss_ratio)
        stop_loss = round(min(stop_by_buffer, stop_by_risk), 3)
        if buy_price >= sell_price:
            return None, None, None, None, 0.0
        take_profit = round(buy_price, 3)
        expected_profit_pct = (sell_price - buy_price) / max(sell_price, 0.001) * 100
        return sell_price, buy_price, stop_loss, take_profit, round(expected_profit_pct, 4)
    return None, None, None, None, 0.0


def attach_trade_costs(
    *,
    symbol: str,
    action: str,
    entry_price: float | None,
    exit_price: float | None,
    quantity: int,
    expected_profit_pct: float,
) -> TradeCostEstimate:
    with SessionLocal() as db:
        if not feature_enabled(db, "t_engine_fee_aware_enabled", True):
            return TradeCostEstimate(net_profit_pct=round(float(expected_profit_pct or 0.0), 2), direction=action)
        if feature_enabled(db, "t_engine_elasticity_enabled", True):
            elasticity = get_trading_elasticity(symbol, db=db)
        else:
            elasticity = None
    return estimate_round_trip_cost(
        symbol=symbol,
        action=action,
        entry_price=entry_price,
        exit_price=exit_price,
        quantity=quantity,
        expected_profit_pct=expected_profit_pct,
        elasticity_score=elasticity.score if elasticity is not None else 0.0,
        elasticity_data_quality=elasticity.data_quality if elasticity is not None else "unavailable",
    )


def negative_buyback_trigger(
    *,
    quote: QuoteSnapshot,
    vwap_value: float,
    ma5: float,
    atr_value: float,
) -> str:
    buffer = max(atr_value * 0.35, quote.last_price * 0.002)
    anchor = _negative_buyback_anchor(ma5=ma5, vwap_value=vwap_value)
    anchor_trigger = max(anchor - buffer, quote.low_price)
    cancel_price = quote.last_price + max(buffer, quote.last_price * 0.003)
    return (
        f"先卖后接回条件：回落至参考价 {anchor_trigger:.3f} 附近，"
        f"且卖压不再放大；若重新站上 {cancel_price:.3f}，取消接回等待。"
    )


def negative_buyback_allowed(
    *,
    buy_price: float,
    vwap_value: float,
    ma5: float,
) -> tuple[bool, str]:
    if vwap_value <= 0 or ma5 <= 0:
        return False, "缺少有效的分时均价线或5日线参考位，不能先卖。"
    max_buyback = _negative_buyback_anchor(ma5=ma5, vwap_value=vwap_value) * 1.003
    if buy_price > max_buyback:
        return False, "计划接回价没有落到分时均价线或5日线下方，卖出后接回约束不足。"
    return True, ""
