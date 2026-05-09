from __future__ import annotations

from typing import Any

from app.core.database import SessionLocal
from app.models.schemas import QuoteSnapshot, SectorSnapshot
from app.services.market.regime import MarketRegimeSnapshot
from app.services.quant_engine_execution_params import (
    asset_bucket,
    dict_param,
    execution_cost_params,
    negative_buyback_anchor,
)
from app.services.quant_engine_market import (
    market_position_multiplier,
    market_risk_reward_shift,
)
from app.services.quant_engine_models import TradeCostEstimate
from app.services.shared.feature_flags import feature_enabled
from app.services.shared.trading_costs import estimate_round_trip_cost
from app.services.shared.trading_elasticity import get_trading_elasticity


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


def net_profit_floor_pct_for_quote(
    quote: QuoteSnapshot,
    action: str,
    sector: SectorSnapshot | None = None,
) -> float:
    """Minimum fee-adjusted edge required before a signal is executable."""

    bucket = asset_bucket(quote, sector)
    params = execution_cost_params()
    floor_map = dict_param(params, "net_profit_floor_pct")
    bucket_values = floor_map.get(bucket) if isinstance(floor_map.get(bucket), dict) else {}
    if not isinstance(bucket_values, dict):
        bucket_values = {}
    default_bucket = {"etf": 0.25, "weight_stock": 0.45 if action == "negative_t" else 0.50}.get(
        bucket,
        0.80 if action == "negative_t" else 0.90,
    )
    try:
        return float(bucket_values.get(action, default_bucket))
    except (TypeError, ValueError):
        return float(default_bucket)


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
        buyback_anchor = negative_buyback_anchor(ma5=ma5, vwap_value=vwap_value)
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
    anchor = negative_buyback_anchor(ma5=ma5, vwap_value=vwap_value)
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
    max_buyback = negative_buyback_anchor(ma5=ma5, vwap_value=vwap_value) * 1.003
    if buy_price > max_buyback:
        return False, "计划接回价没有落到分时均价线或5日线下方，卖出后接回约束不足。"
    return True, ""
