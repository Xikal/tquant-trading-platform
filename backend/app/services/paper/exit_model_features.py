from __future__ import annotations

from datetime import datetime
from math import isfinite
from typing import Any

from app.services.indicators import atr, rsi_wilder, vwap
from app.services.paper.dynamic_exit import primary_strategy_from_position
from app.services.paper.exit_model_schema import EXIT_MODEL_FEATURE_VERSION, ExitModelFeatureSnapshot
from app.services.paper.exit_types import PaperExitDecision
from app.services.paper.quote_quality import PaperQuotePrice
from app.services.paper.smart_exit_context import PaperExitContext


def build_exit_model_features(
    *,
    position: Any,
    decision: PaperExitDecision,
    price: float,
    now: datetime,
    quote: PaperQuotePrice | None = None,
    context: PaperExitContext | None = None,
    intraday_bars: list[Any] | None = None,
    account_total_assets: float = 0.0,
    market_context: dict[str, Any] | None = None,
) -> ExitModelFeatureSnapshot:
    cost = _safe_float(getattr(position, "cost_basis", 0.0))
    quantity = int(getattr(position, "quantity", 0) or 0)
    available = int(getattr(position, "available_quantity", 0) or 0)
    current_price = _safe_float(price or getattr(position, "latest_price", 0.0))
    pnl_pct = (current_price - cost) / cost * 100.0 if cost > 0 and current_price > 0 else 0.0
    opened_at = getattr(position, "opened_at", None)
    hold_days = max((now - opened_at).days, 0) if isinstance(opened_at, datetime) else 0
    trailing_high = _safe_float(getattr(context, "trailing_high_price", 0.0)) if context else 0.0
    quote_high = _safe_float(getattr(quote, "high_price", 0.0)) if quote else 0.0
    max_price = max(trailing_high, quote_high, current_price)
    max_profit_pct = (max_price - cost) / cost * 100.0 if cost > 0 and max_price > 0 else max(pnl_pct, 0.0)
    pullback_from_high_pct = max(max_profit_pct - pnl_pct, 0.0)
    bars = list(intraday_bars or [])
    rsi_value = _rsi_from_bars(bars)
    vwap_value = _safe_float(getattr(context, "vwap", 0.0)) if context else 0.0
    if vwap_value <= 0 and bars:
        vwap_value = vwap(_bars_as_kline_like(bars))
    vwap_deviation_pct = (current_price / vwap_value - 1.0) * 100 if current_price > 0 and vwap_value > 0 else 0.0
    atr_pct = _atr_pct_from_bars(bars, current_price=current_price)
    data_quality, risk_flags = _data_quality(quote=quote, current_price=current_price, bars=bars)
    market = dict(market_context or {})
    rule_action = _rule_action(decision)
    rule_sell_ratio = _safe_float(decision.sell_ratio)
    position_value = current_price * quantity
    position_pct = position_value / account_total_assets * 100.0 if account_total_assets > 0 else 0.0
    feature_values = {
        "pnl_pct": pnl_pct,
        "max_profit_pct": max_profit_pct,
        "pullback_from_high_pct": pullback_from_high_pct,
        "hold_days": float(hold_days),
        "available_ratio": available / max(quantity, 1),
        "position_pct": position_pct,
        "vwap_deviation_pct": vwap_deviation_pct,
        "rsi": rsi_value,
        "atr_pct": atr_pct,
        "high_pullback_ratio": _safe_float(getattr(context, "high_pullback_ratio", 0.0)) if context else 0.0,
        "volume_release_ratio": _safe_float(getattr(context, "volume_release_ratio", 0.0)) if context else 0.0,
        "market_strength": _safe_float(market.get("market_strength")),
        "sector_strength": _safe_float(market.get("sector_strength")),
        "rule_sell_ratio": rule_sell_ratio,
    }
    return ExitModelFeatureSnapshot(
        symbol=str(getattr(position, "symbol", "") or ""),
        name=str(getattr(position, "name", "") or ""),
        strategy_key=primary_strategy_from_position(position),
        as_of=now.isoformat(),
        feature_version=EXIT_MODEL_FEATURE_VERSION,
        current_price=round(current_price, 4),
        cost_basis=round(cost, 4),
        pnl_pct=round(pnl_pct, 4),
        max_profit_pct=round(max_profit_pct, 4),
        pullback_from_high_pct=round(pullback_from_high_pct, 4),
        hold_days=hold_days,
        quantity=quantity,
        available_quantity=available,
        position_pct=round(position_pct, 4),
        rule_action=rule_action,
        rule_sell_ratio=round(rule_sell_ratio, 4),
        quote_quality=str(getattr(quote, "quality", "") or "unavailable") if quote else "unavailable",
        data_quality=data_quality,
        intraday_usable=bool(getattr(context, "intraday_usable", False)) if context else False,
        above_vwap=bool(getattr(context, "above_vwap", False)) if context else False,
        vwap=round(vwap_value, 4),
        vwap_deviation_pct=round(vwap_deviation_pct, 4),
        rsi=round(rsi_value, 4),
        atr_pct=round(atr_pct, 4),
        high_pullback_ratio=round(feature_values["high_pullback_ratio"], 4),
        volume_release_ratio=round(feature_values["volume_release_ratio"], 4),
        trailing_stop_pct=_trailing_stop_pct(context=context, current_price=current_price),
        market_state=str(market.get("market_state") or ""),
        market_strength=round(feature_values["market_strength"], 4),
        sector_strength=round(feature_values["sector_strength"], 4),
        risk_flags=risk_flags,
        feature_values={key: round(value, 6) for key, value in feature_values.items()},
    )


def _rule_action(decision: PaperExitDecision) -> str:
    if decision.action_signal == "hard_stop" or decision.code in {"hard_stop_loss", "etf_stop_loss"}:
        return "hard_stop"
    if decision.quantity <= 0:
        return "hold"
    if decision.sell_ratio >= 0.99:
        return "sell_all"
    if decision.sell_ratio >= 0.69:
        return "sell_70"
    if decision.sell_ratio >= 0.49:
        return "sell_50"
    return "sell_30"


def _data_quality(*, quote: PaperQuotePrice | None, current_price: float, bars: list[Any]) -> tuple[str, list[str]]:
    flags: list[str] = []
    quote_quality = str(getattr(quote, "quality", "") or "").lower() if quote else "missing"
    if current_price <= 0:
        flags.append("invalid_price")
    if quote_quality not in {"fresh", "estimated"}:
        flags.append(f"quote_{quote_quality or 'missing'}")
    if bars and len(bars) < 5:
        flags.append("intraday_short")
    if flags:
        return "partial" if current_price > 0 else "unavailable", flags
    return "fresh", []


def _rsi_from_bars(bars: list[Any]) -> float:
    closes = [_bar_value(bar, "close") for bar in bars if _bar_value(bar, "close") > 0]
    return rsi_wilder(closes, 14) if len(closes) >= 15 else 50.0


def _atr_pct_from_bars(bars: list[Any], *, current_price: float) -> float:
    kline_bars = _bars_as_kline_like(bars)
    atr_value = atr(kline_bars, 14) if len(kline_bars) >= 28 else None
    return float(atr_value or 0.0) / current_price * 100.0 if current_price > 0 and atr_value else 0.0


def _bars_as_kline_like(bars: list[Any]) -> list[Any]:
    return [bar for bar in bars if _bar_value(bar, "close") > 0]


def _bar_value(bar: Any, field: str) -> float:
    return _safe_float(getattr(bar, field, 0.0))


def _safe_float(value: Any) -> float:
    try:
        number = float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
    return number if isfinite(number) else 0.0


def _trailing_stop_pct(*, context: PaperExitContext | None, current_price: float) -> float:
    if context is None or current_price <= 0 or context.trailing_stop_price <= 0:
        return 0.0
    return max((current_price - context.trailing_stop_price) / current_price * 100.0, 0.0)
