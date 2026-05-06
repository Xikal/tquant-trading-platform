from __future__ import annotations

from dataclasses import replace
from typing import Any

from app.models.schemas import AnalysisRequest, MicrostructureSnapshot, QuoteSnapshot, SectorSnapshot, TradingRuleOut
from app.services.market.regime import MarketRegimeSnapshot
from app.services.quant_engine_models import IndicatorSnapshot, ScoreSnapshot, TradePlan
from app.services.quant_engine_output import empty_trade_plan
from app.services.quant_engine_execution import (
    attach_trade_costs,
    estimate_slippage_bps,
    min_profit_pct_for_quote,
    negative_buyback_allowed,
    negative_buyback_trigger,
    min_risk_reward_ratio,
    negative_direction_gate,
    position_pct,
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


def apply_position_constraints(
    action: str,
    request: AnalysisRequest,
    rules: TradingRuleOut,
    blocking_rules: list[str],
) -> tuple[str, list[str]]:
    if action == "positive_t" and request.base_position <= 0 and rules.requires_base_position:
        blocking_rules.append("正T需要底仓支持。")
        return "hold", blocking_rules
    if action == "negative_t" and request.available_position <= 0:
        blocking_rules.append("反T需要可卖底仓支持。")
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
    if "positive_t" in trade_scene.allowed_actions and scores.positive_score >= scores.positive_threshold + 3:
        return "positive_t", blocking_rules
    if "negative_t" in trade_scene.allowed_actions and scores.negative_score >= scores.negative_threshold + 3:
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
) -> tuple[str, list[str]]:
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
    else:
        return action, blocking_rules
    if allowed:
        return action, blocking_rules
    blocking_rules.append(reason)
    return "hold", blocking_rules


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
) -> tuple[TradePlan, list[str]]:
    min_profit_pct = min_profit_pct_for_quote(
        quote=quote,
        config=risk_config,
        tradability_score=scores.tradability_score,
        amplitude=indicators.amplitude,
        market_regime=market_regime,
    )
    if action == "hold":
        return _empty_scene_plan(quote, risk_config, scores, min_profit_pct, trade_scene), blocking_rules

    max_single_loss_pct = max(0.2, float(risk_config.get("risk_max_single_loss_pct", 1.0)))
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
        blocking_rules.append("考虑滑点与风险约束后，当前做T价差不足，建议观望。")
        return _empty_scene_plan(quote, risk_config, scores, min_profit_pct, trade_scene), blocking_rules
    if action == "negative_t":
        allowed_buyback, buyback_reason = negative_buyback_allowed(
            buy_price=exit_price,
            vwap_value=indicators.vwap_value,
            ma5=indicators.ma5,
        )
        if not allowed_buyback:
            blocking_rules.append(buyback_reason)
            return _empty_scene_plan(quote, risk_config, scores, min_profit_pct, trade_scene), blocking_rules
    if expected_profit_pct < min_profit_pct:
        blocking_rules.append(f"预计做T价差仅 {expected_profit_pct:.2f}%，低于最低盈利阈值 {min_profit_pct:.2f}%。")
        return _empty_scene_plan(quote, risk_config, scores, min_profit_pct, trade_scene), blocking_rules

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
    if risk_reward_ratio < min_ratio:
        blocking_rules.append(f"当前盈亏比仅 {risk_reward_ratio:.2f}，低于最低要求 {min_ratio:.2f}。")
        return _empty_scene_plan(quote, risk_config, scores, min_profit_pct, trade_scene), blocking_rules

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
        min_profit_pct=min_profit_pct,
        min_risk_reward_ratio=min_ratio,
        buyback_trigger=buyback_trigger,
        cost_estimate=attach_trade_costs(
            symbol=quote.symbol,
            action=action,
            entry_price=entry_price,
            exit_price=exit_price,
            quantity=_cost_quantity(action=action, request=request, position_pct=position_pct_value),
            expected_profit_pct=expected_profit_pct,
        ),
    )
    return _with_trade_scene(trade_plan, trade_scene), blocking_rules


def _cost_quantity(*, action: str, request: AnalysisRequest, position_pct: float) -> int:
    if action == "negative_t":
        available = max(0, int(request.available_position or 0))
        return _round_lot(max(100, int(available * max(position_pct, 5.0) / 100))) if available > 0 else 0
    base = max(0, int(request.base_position or 0))
    if base <= 0:
        return 0
    return _round_lot(max(100, int(base * max(position_pct, 5.0) / 100)))


def _round_lot(quantity: int) -> int:
    lot = 100
    return max(lot, (int(quantity) // lot) * lot)


def _empty_scene_plan(
    quote: QuoteSnapshot,
    risk_config: dict[str, Any],
    scores: ScoreSnapshot,
    min_profit_pct: float,
    trade_scene: TradeScene | None,
) -> TradePlan:
    return _with_trade_scene(
        empty_trade_plan(
            quote=quote,
            risk_config=risk_config,
            scores=scores,
            min_profit_pct=min_profit_pct,
        ),
        trade_scene,
    )


def _with_trade_scene(trade_plan: TradePlan, trade_scene: TradeScene | None) -> TradePlan:
    if trade_scene is None:
        return trade_plan
    return replace(
        trade_plan,
        trade_scene=trade_scene.key,
        trade_scene_text=trade_scene.label,
    )
