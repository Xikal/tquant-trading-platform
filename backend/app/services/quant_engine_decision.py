from __future__ import annotations

from typing import Any

from app.models.schemas import AnalysisRequest, MicrostructureSnapshot, QuoteSnapshot, SectorSnapshot, TradingRuleOut
from app.services.market.regime import MarketRegimeSnapshot
from app.services.quant_engine_models import IndicatorSnapshot, ScoreSnapshot, TradePlan
from app.services.quant_engine_decision_helpers import (
    cost_quantity as _cost_quantity,
    decision_params as _decision_params,
    empty_scene_plan as _empty_scene_plan,
    last_blocking_rule as _last_blocking_rule,
    light_position_pct as _light_position_pct,
    param_float as _param_float,
    signal_layer_text as _signal_layer_text,
    with_trade_scene as _with_trade_scene,
)
from app.services.quant_engine_execution import (
    attach_trade_costs,
    estimate_slippage_bps,
    light_profit_pct_for_quote,
    min_profit_pct_for_quote,
    negative_buyback_allowed,
    negative_buyback_trigger,
    negative_light_direction_gate,
    negative_prepare_gate,
    min_risk_reward_ratio,
    net_profit_floor_pct_for_quote,
    negative_direction_gate,
    position_pct,
    positive_light_direction_gate,
    positive_prepare_gate,
    positive_direction_gate,
    risk_reward_metrics,
    trade_levels,
)
from app.services.quant_engine_scenes import TradeScene


def resolve_initial_action(
    request: AnalysisRequest,
    scores: ScoreSnapshot,
    blocking_rules: list[str],
) -> str:
    if blocking_rules:
        return "hold"
    preferred_positive = request.prefer_strategy in {"auto", "positive_t"}
    preferred_negative = request.prefer_strategy in {"auto", "negative_t"}
    if preferred_positive and scores.positive_score >= scores.negative_score and scores.positive_score >= scores.positive_threshold:
        return "positive_t"
    if preferred_negative and scores.negative_score > scores.positive_score and scores.negative_score >= scores.negative_threshold:
        return "negative_t"
    return "hold"


def resolve_prepare_action(
    request: AnalysisRequest,
    scores: ScoreSnapshot,
    blocking_rules: list[str],
) -> str:
    """Promote near-threshold scores into the layer gate for watch/light signals."""

    if blocking_rules:
        return "hold"
    params = _decision_params()
    preferred_positive = request.prefer_strategy in {"auto", "positive_t"}
    preferred_negative = request.prefer_strategy in {"auto", "negative_t"}
    near_offset = _param_float(params, "near_threshold_offset", 8.0)
    near_gap = _param_float(params, "near_score_gap", 2.0)
    positive_near = preferred_positive and scores.positive_score >= scores.positive_threshold - near_offset
    negative_near = preferred_negative and scores.negative_score >= scores.negative_threshold - near_offset
    if positive_near and scores.positive_score >= scores.negative_score - near_gap:
        return "positive_t"
    if negative_near and scores.negative_score > scores.positive_score - near_gap:
        return "negative_t"
    return "hold"


def apply_position_constraints(
    action: str,
    request: AnalysisRequest,
    rules: TradingRuleOut,
    blocking_rules: list[str],
) -> tuple[str, list[str]]:
    if action == "positive_t" and request.base_position <= 0 and rules.requires_base_position:
        blocking_rules.append("先买后卖需要已有底仓支持。")
        return "hold", blocking_rules
    if action == "negative_t" and request.available_position <= 0:
        blocking_rules.append("先卖后接回需要有可卖底仓。")
        return "hold", blocking_rules
    return action, blocking_rules


def apply_trade_scene_gate(
    action: str,
    scores: ScoreSnapshot,
    trade_scene: TradeScene,
    blocking_rules: list[str],
) -> tuple[str, list[str]]:
    if action in trade_scene.allowed_actions:
        return action, blocking_rules
    params = _decision_params()
    scene_override_shift = _param_float(params, "scene_override_shift", 3.0)
    if "positive_t" in trade_scene.allowed_actions and scores.positive_score >= scores.positive_threshold + scene_override_shift:
        return "positive_t", blocking_rules
    if "negative_t" in trade_scene.allowed_actions and scores.negative_score >= scores.negative_threshold + scene_override_shift:
        return "negative_t", blocking_rules
    blocking_rules.append(f"场景约束：{trade_scene.label}，{trade_scene.reason}")
    return "hold", blocking_rules


def apply_direction_gate(
    action: str,
    quote: QuoteSnapshot,
    indicators: IndicatorSnapshot,
    sector: SectorSnapshot,
    microstructure: MicrostructureSnapshot,
    blocking_rules: list[str],
    market_regime: MarketRegimeSnapshot | None = None,
) -> tuple[str, list[str], str, str, str]:
    if action == "positive_t":
        allowed, reason = positive_direction_gate(
            quote=quote,
            ma5=indicators.ma5,
            ma20=indicators.ma20,
            slope10=indicators.slope10,
            vwap_value=indicators.vwap_value,
            sector=sector,
            microstructure=microstructure,
            distribution=indicators.distribution,
            market_regime=market_regime,
            intraday_structure=indicators.intraday_structure,
        )
        if allowed:
            return action, blocking_rules, "strong_execute", action, ""
        light_allowed, light_reason = positive_light_direction_gate(
            quote=quote,
            ma5=indicators.ma5,
            ma20=indicators.ma20,
            slope10=indicators.slope10,
            vwap_value=indicators.vwap_value,
            sector=sector,
            microstructure=microstructure,
            distribution=indicators.distribution,
            market_regime=market_regime,
            intraday_structure=indicators.intraday_structure,
        )
        if light_allowed:
            return action, blocking_rules, "light_execute", action, light_reason
        prepare_allowed, prepare_reason = positive_prepare_gate(
            quote=quote,
            ma5=indicators.ma5,
            vwap_value=indicators.vwap_value,
            sector=sector,
            microstructure=microstructure,
            distribution=indicators.distribution,
            market_regime=market_regime,
            intraday_structure=indicators.intraday_structure,
        )
        if prepare_allowed:
            blocking_rules.append(reason)
            return "hold", blocking_rules, "watch_prepare", action, prepare_reason
    elif action == "negative_t":
        allowed, reason = negative_direction_gate(
            quote=quote,
            ma5=indicators.ma5,
            rsi14=indicators.rsi14,
            macd_hist=indicators.macd_hist,
            vwap_value=indicators.vwap_value,
            amplitude=indicators.amplitude,
            sector=sector,
            microstructure=microstructure,
            distribution=indicators.distribution,
            market_regime=market_regime,
            intraday_structure=indicators.intraday_structure,
        )
        if allowed:
            return action, blocking_rules, "strong_execute", action, ""
        light_allowed, light_reason = negative_light_direction_gate(
            quote=quote,
            ma5=indicators.ma5,
            rsi14=indicators.rsi14,
            macd_hist=indicators.macd_hist,
            vwap_value=indicators.vwap_value,
            amplitude=indicators.amplitude,
            sector=sector,
            microstructure=microstructure,
            distribution=indicators.distribution,
            market_regime=market_regime,
            intraday_structure=indicators.intraday_structure,
        )
        if light_allowed:
            return action, blocking_rules, "light_execute", action, light_reason
        prepare_allowed, prepare_reason = negative_prepare_gate(
            quote=quote,
            ma5=indicators.ma5,
            vwap_value=indicators.vwap_value,
            amplitude=indicators.amplitude,
            sector=sector,
            microstructure=microstructure,
            distribution=indicators.distribution,
            market_regime=market_regime,
            intraday_structure=indicators.intraday_structure,
        )
        if prepare_allowed:
            blocking_rules.append(reason)
            return "hold", blocking_rules, "watch_prepare", action, prepare_reason
    else:
        return action, blocking_rules, "hold", "hold", ""
    blocking_rules.append(reason)
    return "hold", blocking_rules, "hold", action, reason


def resolve_trade_plan(
    action: str,
    request: AnalysisRequest,
    quote: QuoteSnapshot,
    indicators: IndicatorSnapshot,
    scores: ScoreSnapshot,
    risk_config: dict[str, Any],
    blocking_rules: list[str],
    market_regime: MarketRegimeSnapshot | None = None,
    trade_scene: TradeScene | None = None,
    sector: SectorSnapshot | None = None,
    signal_layer: str = "hold",
    near_action: str = "hold",
    layer_reason: str = "",
) -> tuple[TradePlan, list[str]]:
    min_profit_pct = min_profit_pct_for_quote(
        quote=quote,
        config=risk_config,
        tradability_score=scores.tradability_score,
        amplitude=indicators.amplitude,
        market_regime=market_regime,
    )
    if action == "hold":
        return _empty_scene_plan(
            quote,
            risk_config,
            scores,
            min_profit_pct,
            trade_scene,
            signal_layer=signal_layer,
            near_action=near_action,
            why_not_execute=layer_reason or _last_blocking_rule(blocking_rules),
        ), blocking_rules

    decision_params = _decision_params()
    max_single_loss_pct = max(
        _param_float(decision_params, "max_single_loss_floor_pct", 0.2),
        float(risk_config.get("risk_max_single_loss_pct", _param_float(decision_params, "default_max_single_loss_pct", 1.0))),
    )
    slippage_bps = estimate_slippage_bps(
        quote=quote,
        tradability_score=scores.tradability_score,
        risk_level=scores.risk_level,
        risk_config=risk_config,
    )
    position_pct_value = position_pct(
        scores.signal_score,
        scores.tradability_score,
        scores.risk_level,
        risk_config,
        quote.instrument_type,
        market_regime,
    )
    light_min_profit_pct = light_profit_pct_for_quote(
        quote=quote,
        sector=sector or SectorSnapshot(sector_name="", sector_strength=0.0, market_strength=0.0, alignment_score=0.0, notes=""),
        market_regime=market_regime,
    )
    entry_price, exit_price, stop_loss, take_profit, expected_profit_pct = trade_levels(
        action=action,
        quote=quote,
        vwap_value=indicators.vwap_value,
        ma5=indicators.ma5,
        atr_value=indicators.atr14,
        slippage_bps=slippage_bps,
        max_single_loss_pct=max_single_loss_pct,
    )
    if entry_price is None or exit_price is None:
        blocking_rules.append("考虑成交偏差和风险后，当前做T价差不足，建议观望。")
        return _empty_scene_plan(
            quote,
            risk_config,
            scores,
            min_profit_pct,
            trade_scene,
            signal_layer="watch_prepare",
            near_action=action,
            why_not_execute=_last_blocking_rule(blocking_rules),
        ), blocking_rules
    if action == "negative_t":
        allowed_buyback, buyback_reason = negative_buyback_allowed(
            buy_price=exit_price,
            vwap_value=indicators.vwap_value,
            ma5=indicators.ma5,
        )
        if not allowed_buyback:
            blocking_rules.append(buyback_reason)
            return _empty_scene_plan(
                quote,
                risk_config,
                scores,
                min_profit_pct,
                trade_scene,
                signal_layer="watch_prepare",
                near_action=action,
                why_not_execute=_last_blocking_rule(blocking_rules),
            ), blocking_rules
    resolved_layer = signal_layer if signal_layer in {"light_execute", "strong_execute"} else "strong_execute"
    if expected_profit_pct < light_min_profit_pct:
        blocking_rules.append(f"预计价差仅 {expected_profit_pct:.2f}%，低于小仓试做最低价差 {light_min_profit_pct:.2f}%。")
        return _empty_scene_plan(
            quote,
            risk_config,
            scores,
            min_profit_pct,
            trade_scene,
            signal_layer="watch_prepare",
            near_action=action,
            why_not_execute=_last_blocking_rule(blocking_rules),
        ), blocking_rules
    if expected_profit_pct < min_profit_pct:
        resolved_layer = "light_execute"

    risk_reward_ratio = 0.0
    expected_loss_pct = 0.0
    min_ratio = min_risk_reward_ratio(quote, action, market_regime)
    if stop_loss is not None:
        risk_reward_ratio, expected_loss_pct = risk_reward_metrics(
            action=action,
            entry_price=entry_price,
            exit_price=exit_price,
            stop_loss=stop_loss,
        )
    light_min_ratio = max(
        _param_float(decision_params, "light_min_ratio_floor", 0.8),
        min_ratio - _param_float(decision_params, "light_min_ratio_discount", 0.22),
    )
    if risk_reward_ratio < light_min_ratio:
        blocking_rules.append(f"当前收益和风险不划算，低于小仓试做最低要求 {light_min_ratio:.2f}。")
        return _empty_scene_plan(
            quote,
            risk_config,
            scores,
            min_profit_pct,
            trade_scene,
            signal_layer="watch_prepare",
            near_action=action,
            why_not_execute=_last_blocking_rule(blocking_rules),
        ), blocking_rules
    if risk_reward_ratio < min_ratio:
        resolved_layer = "light_execute"
    if resolved_layer == "light_execute":
        position_pct_value = _light_position_pct(position_pct_value, quote)
        min_profit_for_plan = light_min_profit_pct
        min_ratio_for_plan = light_min_ratio
    else:
        min_profit_for_plan = min_profit_pct
        min_ratio_for_plan = min_ratio

    buyback_trigger = (
        negative_buyback_trigger(
            quote=quote,
            vwap_value=indicators.vwap_value,
            ma5=indicators.ma5,
            atr_value=indicators.atr14,
        )
        if action == "negative_t"
        else ""
    )
    cost_estimate = attach_trade_costs(
        symbol=quote.symbol,
        action=action,
        entry_price=entry_price,
        exit_price=exit_price,
        quantity=_cost_quantity(action=action, request=request, position_pct=position_pct_value),
        expected_profit_pct=expected_profit_pct,
    )
    net_floor = net_profit_floor_pct_for_quote(quote=quote, action=action, sector=sector)
    if cost_estimate is not None and cost_estimate.net_profit_pct < net_floor:
        blocking_rules.append(
            f"扣手续费后预计收益仅 {cost_estimate.net_profit_pct:.2f}%，低于可执行最低要求 {net_floor:.2f}%。"
        )
        return _empty_scene_plan(
            quote,
            risk_config,
            scores,
            min_profit_pct,
            trade_scene,
            signal_layer="watch_prepare",
            near_action=action,
            why_not_execute=_last_blocking_rule(blocking_rules),
        ), blocking_rules

    trade_plan = TradePlan(
        action=action,
        entry_price=entry_price,
        exit_price=exit_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        position_pct=position_pct_value,
        expected_profit_pct=expected_profit_pct,
        expected_loss_pct=expected_loss_pct,
        risk_reward_ratio=risk_reward_ratio,
        slippage_bps=slippage_bps,
        min_profit_pct=min_profit_for_plan,
        min_risk_reward_ratio=min_ratio_for_plan,
        buyback_trigger=buyback_trigger,
        cost_estimate=cost_estimate,
        signal_layer=resolved_layer,
        signal_layer_text=_signal_layer_text(resolved_layer, action),
        near_action=action,
        why_not_execute=layer_reason if resolved_layer == "light_execute" else "",
    )
    return _with_trade_scene(trade_plan, trade_scene), blocking_rules
