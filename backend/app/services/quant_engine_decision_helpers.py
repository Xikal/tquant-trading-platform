from __future__ import annotations

from dataclasses import replace
from typing import Any

from app.models.schemas import AnalysisRequest, QuoteSnapshot
from app.services.quant_engine_models import ScoreSnapshot, TradePlan
from app.services.quant_engine_output import empty_trade_plan
from app.services.quant_engine_scenes import TradeScene


def decision_params() -> dict[str, Any]:
    from app.services.low_buy.strategy_parameter_defaults import POSITION_T_DECISION_DEFAULTS
    from app.services.quant.runtime_parameters import get_position_t_decision

    values = get_position_t_decision()
    return {**POSITION_T_DECISION_DEFAULTS, **values} if isinstance(values, dict) else dict(POSITION_T_DECISION_DEFAULTS)


def param_float(params: dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        return float(params.get(key, default))
    except (TypeError, ValueError):
        return float(default)


def param_int(params: dict[str, Any], key: str, default: int = 0) -> int:
    return int(round(param_float(params, key, float(default))))


def cost_quantity(*, action: str, request: AnalysisRequest, position_pct: float) -> int:
    params = decision_params()
    lot_size = param_int(params, "lot_size", 100)
    min_pct = param_float(params, "min_position_pct_for_cost", 5.0)
    if action == "negative_t":
        available = max(0, int(request.available_position or 0))
        return round_lot(max(lot_size, int(available * max(position_pct, min_pct) / 100)), lot_size=lot_size) if available > 0 else 0
    base = max(0, int(request.base_position or 0))
    if base <= 0:
        return 0
    return round_lot(max(lot_size, int(base * max(position_pct, min_pct) / 100)), lot_size=lot_size)


def round_lot(quantity: int, *, lot_size: int = 100) -> int:
    lot = max(int(lot_size or 100), 1)
    return max(lot, (int(quantity) // lot) * lot)


def light_position_pct(position_pct_value: float, quote: QuoteSnapshot) -> float:
    params = decision_params()
    cap = (
        param_float(params, "light_position_etf_cap_pct", 10.0)
        if quote.instrument_type == "etf"
        else param_float(params, "light_position_stock_cap_pct", 8.0)
    )
    return round(
        max(
            param_float(params, "light_position_min_pct", 5.0),
            min(cap, position_pct_value * param_float(params, "light_position_multiplier", 0.45)),
        ),
        2,
    )


def empty_scene_plan(
    quote: QuoteSnapshot,
    risk_config: dict[str, Any],
    scores: ScoreSnapshot,
    min_profit_pct: float,
    trade_scene: TradeScene | None,
    signal_layer: str = "hold",
    near_action: str = "hold",
    why_not_execute: str = "",
) -> TradePlan:
    return with_signal_layer(
        with_trade_scene(
            empty_trade_plan(
                quote=quote,
                risk_config=risk_config,
                scores=scores,
                min_profit_pct=min_profit_pct,
            ),
            trade_scene,
        ),
        signal_layer=signal_layer,
        near_action=near_action,
        why_not_execute=why_not_execute,
    )


def with_trade_scene(trade_plan: TradePlan, trade_scene: TradeScene | None) -> TradePlan:
    if trade_scene is None:
        return trade_plan
    return replace(
        trade_plan,
        trade_scene=trade_scene.key,
        trade_scene_text=trade_scene.label,
    )


def with_signal_layer(
    trade_plan: TradePlan,
    *,
    signal_layer: str,
    near_action: str,
    why_not_execute: str,
) -> TradePlan:
    return replace(
        trade_plan,
        signal_layer=signal_layer,
        signal_layer_text=signal_layer_text(signal_layer, near_action),
        near_action=near_action,
        why_not_execute=why_not_execute,
    )


def signal_layer_text(signal_layer: str, action: str) -> str:
    if signal_layer == "strong_execute":
        return "可以按计划操作"
    if signal_layer == "light_execute":
        return "只适合小仓试做"
    if signal_layer == "watch_prepare":
        if action == "positive_t":
            return "接近先买后卖机会"
        if action == "negative_t":
            return "接近先卖后接回机会"
        return "接近信号"
    return "今天不做"


def last_blocking_rule(blocking_rules: list[str]) -> str:
    for rule in reversed(blocking_rules):
        cleaned = str(rule).strip()
        if cleaned:
            return cleaned
    return ""
