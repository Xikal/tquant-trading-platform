from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_CEILING

from app.services.paper.fees import calculate_fee, commission_warning_text
from app.services.paper.symbols import is_etf
from app.services.quant_engine_models import TradeCostEstimate


def estimate_round_trip_cost(
    *,
    symbol: str,
    action: str,
    entry_price: float | None,
    exit_price: float | None,
    quantity: int,
    expected_profit_pct: float,
    elasticity_score: float = 0.0,
    elasticity_data_quality: str = "unavailable",
) -> TradeCostEstimate:
    """Estimate round-trip fee drag for T signals.

    This is intentionally conservative and shared by quant analysis and paper
    risk checks so UI hints, admission checks and reports use one fee model.
    """

    entry = _decimal_price(entry_price)
    exit_ = _decimal_price(exit_price)
    safe_quantity = max(0, int(quantity or 0))
    if entry <= 0 or safe_quantity <= 0:
        return TradeCostEstimate(
            net_profit_pct=round(float(expected_profit_pct or 0.0), 2),
            elasticity_score=round(elasticity_score, 2),
            elasticity_data_quality=elasticity_data_quality,
            elasticity_tier=_elasticity_tier(elasticity_score, elasticity_data_quality),
        )

    entry_side = "buy" if action == "positive_t" else "sell"
    exit_side = "sell" if entry_side == "buy" else "buy"
    current_fee = calculate_fee(symbol=symbol, side=entry_side, price=entry, quantity=safe_quantity)
    exit_fee = calculate_fee(symbol=symbol, side=exit_side, price=exit_ if exit_ > 0 else entry, quantity=safe_quantity)
    total_fee = current_fee.total_fee + exit_fee.total_fee
    gross = current_fee.gross_amount
    breakeven_pct = float((total_fee / gross * Decimal("100")) if gross > 0 else Decimal("0"))
    estimated_fee = float(total_fee)
    net_profit_pct = round(float(expected_profit_pct or 0.0) - breakeven_pct, 2)
    liquidity_warning = _liquidity_warning(
        symbol=symbol,
        breakeven_pct=breakeven_pct,
        elasticity_score=elasticity_score,
        data_quality=elasticity_data_quality,
    )
    return TradeCostEstimate(
        estimated_fee=round(estimated_fee, 2),
        net_profit_pct=net_profit_pct,
        breakeven_pct=round(breakeven_pct, 2),
        fee_warning=commission_warning_text(gross_amount=gross, total_fee=total_fee),
        elasticity_score=round(elasticity_score, 2),
        elasticity_data_quality=elasticity_data_quality,
        elasticity_tier=_elasticity_tier(elasticity_score, elasticity_data_quality),
        liquidity_warning=liquidity_warning,
        suggested_timing=_suggested_timing(action, net_profit_pct, elasticity_score),
        min_position_value=_min_position_value(symbol),
        direction=action,
        min_shares_suggestion=_min_shares_suggestion(symbol, entry),
    )


def round_trip_fee_pct(*, symbol: str, side: str, price: Decimal, quantity: int) -> float:
    if price <= 0 or quantity <= 0:
        return 0.0
    entry_side = "buy" if side == "buy" else "sell"
    exit_side = "sell" if entry_side == "buy" else "buy"
    current_fee = calculate_fee(symbol=symbol, side=entry_side, price=price, quantity=quantity).total_fee
    exit_fee = calculate_fee(symbol=symbol, side=exit_side, price=price, quantity=quantity).total_fee
    gross = price * Decimal(quantity)
    if gross <= 0:
        return 0.0
    return float((current_fee + exit_fee) / gross * Decimal("100"))


def _decimal_price(value: float | None) -> Decimal:
    try:
        return Decimal(str(value or 0))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _elasticity_tier(score: float, data_quality: str) -> str:
    if data_quality != "ok":
        return "★★"
    if score >= 75:
        return "★★★★★"
    if score >= 50:
        return "★★★★"
    if score >= 25:
        return "★★★"
    return "★★"


def _liquidity_warning(*, symbol: str, breakeven_pct: float, elasticity_score: float, data_quality: str) -> str:
    if breakeven_pct >= 0.8:
        return "单笔金额偏小，手续费会明显吞噬做T收益。"
    if data_quality == "ok" and elasticity_score < 35:
        return "近期冲高弹性较弱，做T空间不足。"
    if is_etf(symbol):
        return ""
    return ""


def _suggested_timing(action: str, net_profit_pct: float, elasticity_score: float) -> str:
    if net_profit_pct <= 0:
        return "价差扣费后不划算，等待更好位置。"
    if action == "positive_t":
        return "只在回踩承接并重新站回 VWAP 后执行。"
    if action == "negative_t":
        return "只在冲高衰竭且回补价差足够时执行。"
    if elasticity_score >= 70:
        return "可优先观察早盘第一波确认。"
    return ""


def _min_position_value(symbol: str) -> float:
    return 3000.0 if is_etf(symbol) else 8000.0


def _min_shares_suggestion(symbol: str, price: Decimal) -> int:
    min_value = Decimal(str(_min_position_value(symbol)))
    if price <= 0:
        return 0
    shares = int((min_value / price).to_integral_value(rounding=ROUND_CEILING))
    lot = 100
    return max(lot, ((shares + lot - 1) // lot) * lot)
