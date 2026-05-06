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


def estimate_slippage_bps(
    quote: QuoteSnapshot,
    tradability_score: float,
    risk_level: str,
    risk_config: dict[str, Any],
) -> float:
    baseline = (
        config_float(risk_config, "strategy_slippage_etf_bps", 4.0)
        if quote.instrument_type == "etf"
        else config_float(risk_config, "strategy_slippage_stock_bps", 7.0)
    )
    liquidity_penalty = max(0.0, 60 - tradability_score) * 0.18
    if risk_level == "medium":
        baseline += 1.5
    elif risk_level == "high":
        baseline += 3.5
    return round(max(2.0, min(25.0, baseline + liquidity_penalty)), 2)


def min_profit_pct_for_quote(
    quote: QuoteSnapshot,
    config: dict[str, Any],
    tradability_score: float,
    amplitude: float,
    market_regime: MarketRegimeSnapshot | None = None,
) -> float:
    legacy_default = config_float(config, "strategy_min_profit_pct", 3.0)
    tradability_bonus = 0.0
    amplitude_bonus = 0.0
    liquidity_bonus = 0.0
    if tradability_score >= 76:
        tradability_bonus = 0.45
    elif tradability_score >= 64:
        tradability_bonus = 0.28
    elif tradability_score >= 56:
        tradability_bonus = 0.16
    if 0 < amplitude <= 2.0:
        amplitude_bonus = 0.2
    elif 0 < amplitude <= 2.8:
        amplitude_bonus = 0.12
    if quote.instrument_type == "etf":
        base = config_float(config, "strategy_min_profit_etf_pct", max(1.5, legacy_default))
        if quote.amount >= 800_000_000:
            liquidity_bonus = 0.25
        elif quote.amount >= 400_000_000:
            liquidity_bonus = 0.18
        elif quote.amount >= 250_000_000:
            liquidity_bonus = 0.12
        adjusted = base - tradability_bonus - amplitude_bonus - liquidity_bonus + market_profit_threshold_shift(
            market_regime,
            instrument_type=quote.instrument_type,
        )
        return round(max(0.6, adjusted), 2)
    base = config_float(config, "strategy_min_profit_stock_pct", legacy_default)
    if quote.amount >= 150_000_000:
        tradability_bonus += 0.25
    if quote.amount >= 800_000_000:
        liquidity_bonus = 0.38
    elif quote.amount >= 400_000_000:
        liquidity_bonus = 0.25
    elif quote.amount >= 250_000_000:
        liquidity_bonus = 0.12
    adjusted = base - tradability_bonus - amplitude_bonus - liquidity_bonus + market_profit_threshold_shift(
        market_regime,
        instrument_type=quote.instrument_type,
    )
    return round(max(1.5, adjusted), 2)


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
    price_extension_limit = 1.035
    weak_vwap_limit = 0.992
    slope_floor = -0.26
    weak_sector_floor = 44.0
    weak_buy_pressure_floor = 44.0
    state = market_regime.state if market_regime is not None else "low_volume_wait"
    if asset_bucket == "etf" and state == "weight_support":
        price_extension_limit = 1.042
        weak_vwap_limit = 0.989
        slope_floor = -0.34
    elif asset_bucket == "etf" and state == "weight_support_active":
        price_extension_limit = 1.038
        weak_vwap_limit = 0.991
        slope_floor = -0.30
    elif asset_bucket == "weight_stock" and state == "weight_support":
        price_extension_limit = 1.040
        weak_vwap_limit = 0.990
        slope_floor = -0.32
        weak_sector_floor = 38.0
        weak_buy_pressure_floor = 40.0
    elif asset_bucket == "weight_stock" and state == "weight_support_active":
        price_extension_limit = 1.037
        weak_vwap_limit = 0.991
        slope_floor = -0.28
        weak_sector_floor = 40.0
        weak_buy_pressure_floor = 41.0
    elif asset_bucket == "thematic_stock" and state == "weight_support":
        price_extension_limit = 1.029
        weak_vwap_limit = 0.995
        slope_floor = -0.16
        weak_sector_floor = 48.0
        weak_buy_pressure_floor = 48.0
    elif asset_bucket == "thematic_stock" and state == "weight_support_active":
        price_extension_limit = 1.032
        weak_vwap_limit = 0.993
        weak_sector_floor = 42.0
        weak_buy_pressure_floor = 42.0
    elif asset_bucket == "thematic_stock" and state == "fast_rotation":
        price_extension_limit = 1.028
        weak_vwap_limit = 0.995
        slope_floor = -0.08
        weak_sector_floor = 50.0
        weak_buy_pressure_floor = 50.0
    if state in {"high_flyer_retreat", "risk_release"} and asset_bucket != "etf":
        if asset_bucket == "weight_stock":
            price_extension_limit = 1.032
            weak_vwap_limit = 0.994
            weak_sector_floor = 42.0
            weak_buy_pressure_floor = 44.0
        else:
            price_extension_limit = 1.026
            weak_vwap_limit = 0.996
            slope_floor = -0.10
            weak_sector_floor = 48.0
            weak_buy_pressure_floor = 48.0
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
        return False, "题材股处在退潮/快速轮动环境，必须等板块和盘口同时转强后再做正T。"
    if intraday_structure != "pullback_acceptance":
        return False, "正T只做回踩承接：必须先回踩 VWAP/MA5，再重新站回 VWAP，且近几根分钟 K 低点抬高、回踩量能收缩。"
    if quote.last_price < vwap_value * 1.001:
        return False, "正T需要重新站回 VWAP 后再执行。"
    if quote.last_price > ma5 * price_extension_limit:
        return False, "价格已显著偏离短均线，正T不建议追价。"
    if quote.last_price < ma20 * 0.992:
        return False, "价格已经回落到中期均线下方，当前不适合执行正T。"
    if slope10 < slope_floor:
        return False, "短线斜率转弱，正T顺势优势不足。"
    weak_sector = sector.alignment_score < weak_sector_floor
    if asset_bucket == "weight_stock":
        weak_sector = weak_sector and state not in {"weight_support", "weight_support_active"}
    weak_buy_pressure = microstructure.available and microstructure.buy_pressure < weak_buy_pressure_floor
    weak_vwap = quote.last_price < vwap_value * weak_vwap_limit
    if weak_sector and weak_buy_pressure:
        return False, "板块联动和盘口承接同时偏弱，正T胜率不足。"
    if weak_vwap and slope10 < -0.12:
        return False, "价格仍弱于 VWAP，先等回到均价附近再考虑正T。"
    return True, ""


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
        return False, "反T只做冲高衰竭：需要冲高钝化、放量滞涨或假突破结构，横盘小波动不先卖。"
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
        return False, "日内振幅不足，反T的冲高回落空间不够。"
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
        return False, "价格并未明显强于短线均价，反T不适合先卖。"
    if rsi14 < (56 if not distribution_bias else 53) and macd_hist >= 0.02:
        return False, "短线并未进入偏热区，反T先卖优势不足。"
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
        return False, "盘口抛压不明显，反T先卖胜率不足。"
    return True, ""


def _negative_buyback_room_allowed(
    *,
    quote: QuoteSnapshot,
    ma5: float,
    vwap_value: float,
    asset_bucket: str,
    distribution_bias: bool,
) -> tuple[bool, str]:
    if quote.last_price <= 0 or ma5 <= 0 or vwap_value <= 0:
        return False, "反T缺少有效 VWAP/MA5 回补锚点，不能先卖。"
    buyback_anchor = _negative_buyback_anchor(ma5=ma5, vwap_value=vwap_value)
    distance_to_reference_pct = (quote.last_price - buyback_anchor) / max(quote.last_price, 0.01) * 100
    min_distance = {"etf": 0.35, "weight_stock": 0.55}.get(asset_bucket, 0.75)
    if distribution_bias:
        min_distance *= 0.75
    if distance_to_reference_pct < min_distance:
        return False, "反T卖后回补空间不足，当前价距离 VWAP/MA5 太近。"
    near_intraday_high = quote.high_price > 0 and quote.last_price >= quote.high_price * (0.982 if distribution_bias else 0.988)
    if not near_intraday_high:
        return False, "反T需要在分时高位附近处理，当前位置不是冲高衰竭区。"
    estimated_buyback = buyback_anchor * 0.998
    round_trip_cost = {"etf": 0.12, "weight_stock": 0.22}.get(asset_bucket, 0.28)
    min_net_room = {"etf": 0.28, "weight_stock": 0.42}.get(asset_bucket, 0.55)
    net_room = (quote.last_price - estimated_buyback) / max(quote.last_price, 0.01) * 100 - round_trip_cost
    if net_room < min_net_room:
        return False, "扣除双边成本和滑点后，反T回补净空间不足。"
    return True, ""


def _negative_buyback_anchor(*, ma5: float, vwap_value: float) -> float:
    return min(ma5, vwap_value)


def _positive_distribution_block(
    *,
    asset_bucket: str,
    state: str,
    distribution: DistributionSnapshot,
) -> str:
    if distribution.false_breakout_flag:
        return "分时出现假突破回落，正T不适合逆着派发迹象追买。"
    if distribution.intraday_reversal_flag and distribution.distribution_risk_score >= (8.2 if asset_bucket == "etf" else 7.0):
        return "分时冲高回落明显，正T先等派发压力释放。"
    weak_stall_context = state in {"fast_rotation", "high_flyer_retreat", "risk_release"}
    if distribution.stall_after_volume_flag and asset_bucket == "thematic_stock" and weak_stall_context:
        return "放量滞涨叠加弱环境，正T胜率不足。"
    if distribution.distribution_risk_score >= (8.8 if asset_bucket == "etf" else 7.8):
        return "当前派发风险偏高，正T应等待更强承接。"
    return ""


def _thematic_positive_state_block(
    *,
    asset_bucket: str,
    state: str,
    sector: SectorSnapshot,
    microstructure: MicrostructureSnapshot,
) -> bool:
    if asset_bucket != "thematic_stock" or state not in {"fast_rotation", "high_flyer_retreat", "risk_release"}:
        return False
    if not microstructure.available:
        return sector.alignment_score < 55.0
    return sector.alignment_score < 55.0 or microstructure.buy_pressure < 55.0


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
        elasticity_data_quality=elasticity.data_quality if elasticity is not None else "disabled",
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
        f"反T回补条件：回落至回补锚点 {anchor_trigger:.3f} 附近，"
        f"且抛压不再放大；若重新站上 {cancel_price:.3f}，取消回补等待。"
    )


def negative_buyback_allowed(
    *,
    buy_price: float,
    vwap_value: float,
    ma5: float,
) -> tuple[bool, str]:
    if vwap_value <= 0 or ma5 <= 0:
        return False, "反T缺少有效 VWAP/MA5 回补锚点，不能先卖。"
    max_buyback = _negative_buyback_anchor(ma5=ma5, vwap_value=vwap_value) * 1.003
    if buy_price > max_buyback:
        return False, "反T回补价没有落到 VWAP/MA5 下方，卖出后回补约束不足。"
    return True, ""
