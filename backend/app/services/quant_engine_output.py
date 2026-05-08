from __future__ import annotations

from typing import Any

from app.models.schemas import QuoteSnapshot, StrategySuggestion, TradingRuleOut
from app.services.market.regime import MarketRegimeSnapshot
from app.services.indicators import sanitize_metrics
from app.services.quant_engine_models import IndicatorSnapshot, ScoreSnapshot, TradePlan
from app.services.quant_engine_common import config_float, price_limit_pct, strategy_note
from app.services.quant_engine_execution import estimate_slippage_bps
from app.services.quant_engine_market import market_state_description, market_state_text


def build_assumptions(base_position: int, available_position: int) -> list[str]:
    if base_position == 1000 and available_position == 1000:
        return ["未提供真实持仓时，系统按 1000 股底仓做研究模式估算。"]
    return []


def build_compliance_notes(
    quote: QuoteSnapshot,
    trade_plan: TradePlan,
    scores: ScoreSnapshot,
    market_regime: MarketRegimeSnapshot | None,
) -> list[str]:
    notes: list[str] = []
    notes.append(f"当前市场状态：{market_state_text(market_regime)}。{market_state_description(market_regime)}")
    if scores.risk_level == "high":
        notes.append("风险等级较高，建议降低仓位并放宽执行频率。")
    notes.append(f"买卖价格已按约 {trade_plan.slippage_bps / 100:.3f}% 的成交偏差保守估算。")
    if trade_plan.trade_scene_text:
        notes.append(f"做T场景：{trade_plan.trade_scene_text}。")
    notes.append(f"操作状态：{trade_plan.signal_layer_text}。")
    if trade_plan.why_not_execute:
        notes.append(f"未执行原因：{trade_plan.why_not_execute}")
    if trade_plan.buyback_trigger:
        notes.append(trade_plan.buyback_trigger)
    notes.append(f"机会强度要求：先买后卖≥{scores.positive_threshold:.1f}，先卖后接回≥{scores.negative_threshold:.1f}。")
    instrument_label = "ETF" if quote.instrument_type == "etf" else "股票"
    notes.append(f"{instrument_label}至少需要约 {trade_plan.min_profit_pct:.2f}% 的价差才值得操作。")
    if trade_plan.risk_reward_ratio > 0:
        notes.append(
            f"预估收益约为风险的 {trade_plan.risk_reward_ratio:.2f} 倍，若失败约亏 {trade_plan.expected_loss_pct:.2f}%。"
        )
    return notes


def build_metrics(
    quote: QuoteSnapshot,
    indicators: IndicatorSnapshot,
    scores: ScoreSnapshot,
    trade_plan: TradePlan,
    risk_config: dict[str, Any],
    market_regime: MarketRegimeSnapshot | None,
) -> dict[str, Any]:
    metrics = sanitize_metrics(
        {
            "ma5": indicators.ma5,
            "ma20": indicators.ma20,
            "ma60": indicators.ma60,
            "rsi14": indicators.rsi14,
            "macd_dif": indicators.macd_dif,
            "macd_dea": indicators.macd_dea,
            "macd_hist": indicators.macd_hist,
            "vwap": indicators.vwap_value,
            "atr14": indicators.atr14,
            "volume_ratio": indicators.volume_ratio_value,
            "amplitude_pct": indicators.amplitude,
            "slope10_pct": indicators.slope10,
            "obv": indicators.obv_value,
            "positive_score": scores.positive_score,
            "negative_score": scores.negative_score,
            "event_penalty": scores.event_penalty,
            "risk_score": scores.risk_score,
            "slippage_bps": trade_plan.slippage_bps,
            "positive_threshold": scores.positive_threshold,
            "negative_threshold": scores.negative_threshold,
            "market_state_bonus": scores.market_bonus,
            "distribution_risk_score": indicators.distribution.distribution_risk_score,
            "false_breakout_flag": indicators.distribution.false_breakout_flag,
            "stall_after_volume_flag": indicators.distribution.stall_after_volume_flag,
            "intraday_reversal_flag": indicators.distribution.intraday_reversal_flag,
            "expected_profit_pct": trade_plan.expected_profit_pct,
            "expected_loss_pct": trade_plan.expected_loss_pct,
            "risk_reward_ratio": trade_plan.risk_reward_ratio,
            "min_profit_pct": trade_plan.min_profit_pct,
            "min_risk_reward_ratio": trade_plan.min_risk_reward_ratio,
            "intraday_structure": indicators.intraday_structure,
            "min_profit_stock_pct": config_float(
                risk_config,
                "strategy_min_profit_stock_pct",
                config_float(risk_config, "strategy_min_profit_pct", 3.0),
            ),
            "min_profit_etf_pct": config_float(
                risk_config,
                "strategy_min_profit_etf_pct",
                max(1.5, config_float(risk_config, "strategy_min_profit_pct", 3.0)),
            ),
            "price_limit_pct": price_limit_pct(
                quote.symbol,
                quote.instrument_type,
                is_st=str(quote.name or "").upper().startswith(("ST", "*ST")),
            ),
        }
    )
    metrics["scenario"] = scores.scenario
    metrics["trade_scene"] = trade_plan.trade_scene
    metrics["trade_scene_text"] = trade_plan.trade_scene_text
    metrics["signal_layer"] = trade_plan.signal_layer
    metrics["signal_layer_text"] = trade_plan.signal_layer_text
    metrics["near_action"] = trade_plan.near_action
    metrics["why_not_execute"] = trade_plan.why_not_execute
    metrics["intraday_structure_text"] = indicators.intraday_structure_text
    metrics["buyback_trigger"] = trade_plan.buyback_trigger
    metrics["market_state"] = scores.market_state
    metrics["market_state_text"] = scores.market_state_text
    metrics["market_state_description"] = market_state_description(market_regime)
    return metrics


def build_suggestion(
    action: str,
    trade_plan: TradePlan,
    scores: ScoreSnapshot,
    reasons: list[str],
    blocking_rules: list[str],
    rules: TradingRuleOut,
) -> StrategySuggestion:
    plain = _plain_t_decision(action=action, trade_plan=trade_plan, blocking_rules=blocking_rules)
    cost = trade_plan.cost_estimate
    cost_pass = cost is None or cost.net_profit_pct > 0
    actionable = (
        action in {"positive_t", "negative_t"}
        and trade_plan.signal_layer in {"light_execute", "strong_execute"}
        and not blocking_rules
        and cost_pass
    )
    effective_action = action if actionable else "hold"
    return StrategySuggestion(
        action=action,  # type: ignore[arg-type]
        entry_price=trade_plan.entry_price,
        exit_price=trade_plan.exit_price,
        position_pct=trade_plan.position_pct,
        stop_loss=trade_plan.stop_loss,
        risk_level=scores.risk_level,  # type: ignore[arg-type]
        signal_score=round(max(0.0, min(100.0, scores.signal_score)), 2),
        tradability_score=round(scores.tradability_score, 2),
        confidence=round(max(0.0, min(100.0, scores.signal_score - scores.risk_score * 0.15)), 2),
        expected_profit_pct=round(trade_plan.expected_profit_pct, 2),
        scenario=scores.scenario,
        trade_scene=trade_plan.trade_scene,
        trade_scene_text=trade_plan.trade_scene_text,
        signal_layer=trade_plan.signal_layer,
        signal_layer_text=trade_plan.signal_layer_text,
        near_action=trade_plan.near_action,  # type: ignore[arg-type]
        why_not_execute=trade_plan.why_not_execute,
        buyback_trigger=trade_plan.buyback_trigger,
        reasons=reasons,
        blocking_rules=list(dict.fromkeys(blocking_rules)),
        take_profit=trade_plan.take_profit,
        strategy_notes=strategy_note(action, rules.turnaround_mode),
        plain_action_text=plain["plain_action_text"],
        plain_action_reason=plain["plain_action_reason"],
        plain_execution_text=plain["plain_execution_text"],
        plain_invalid_condition=plain["plain_invalid_condition"],
        estimated_fee=cost.estimated_fee if cost is not None else 0.0,
        net_profit_pct=cost.net_profit_pct if cost is not None else trade_plan.expected_profit_pct,
        breakeven_pct=cost.breakeven_pct if cost is not None else 0.0,
        fee_warning=cost.fee_warning if cost is not None else "",
        elasticity_score=cost.elasticity_score if cost is not None else 0.0,
        elasticity_data_quality=cost.elasticity_data_quality if cost is not None else "unavailable",
        elasticity_tier=cost.elasticity_tier if cost is not None else "",
        liquidity_warning=cost.liquidity_warning if cost is not None else "",
        suggested_timing=cost.suggested_timing if cost is not None else "",
        min_position_value=cost.min_position_value if cost is not None else 0.0,
        direction=cost.direction if cost is not None else action,
        min_shares_suggestion=cost.min_shares_suggestion if cost is not None else 0,
        effective_action=effective_action,  # type: ignore[arg-type]
        is_actionable=actionable,
    )


def empty_trade_plan(
    quote: QuoteSnapshot,
    risk_config: dict[str, Any],
    scores: ScoreSnapshot,
    min_profit_pct: float,
) -> TradePlan:
    return TradePlan(
        action="hold",
        entry_price=None,
        exit_price=None,
        stop_loss=None,
        take_profit=None,
        position_pct=0.0,
        expected_profit_pct=0.0,
        expected_loss_pct=0.0,
        risk_reward_ratio=0.0,
        slippage_bps=estimate_slippage_bps(
            quote=quote,
            tradability_score=scores.tradability_score,
            risk_level=scores.risk_level,
            risk_config=risk_config,
        ),
        min_profit_pct=min_profit_pct,
        min_risk_reward_ratio=0.0,
        signal_layer="hold",
        signal_layer_text="今天不做",
        near_action="hold",
    )


def _plain_t_decision(
    *,
    action: str,
    trade_plan: TradePlan,
    blocking_rules: list[str],
) -> dict[str, str]:
    if trade_plan.signal_layer == "watch_prepare":
        return _watch_prepare_plain_text(trade_plan, blocking_rules)
    if trade_plan.signal_layer == "light_execute" and action in {"positive_t", "negative_t"}:
        base = _positive_t_plain_text(trade_plan) if action == "positive_t" else _negative_t_plain_text(trade_plan)
        base["plain_action_text"] = "只适合小仓试做"
        base["plain_action_reason"] = trade_plan.why_not_execute or "条件还没到最稳，只能小仓试做，并且必须看扣手续费后是否划算。"
        return base
    if action == "positive_t":
        return _positive_t_plain_text(trade_plan)
    if action == "negative_t":
        return _negative_t_plain_text(trade_plan)
    return _hold_plain_text(blocking_rules)


def _watch_prepare_plain_text(trade_plan: TradePlan, blocking_rules: list[str]) -> dict[str, str]:
    near_action = trade_plan.near_action
    direction = "先买后卖" if near_action == "positive_t" else "先卖后接回" if near_action == "negative_t" else "做T"
    reason = trade_plan.why_not_execute or _first_blocker(blocking_rules)
    if near_action == "positive_t":
        execution = "先不下单；等重新站稳分时均价线、低点抬高，并且扣手续费后仍划算，再考虑先买后卖。"
        invalid = "如果跌破分时均价线或 5 日线，或者板块继续转弱，取消这次机会。"
    elif near_action == "negative_t":
        execution = "先不卖；等冲高变弱、回落接回空间扣手续费后仍划算，再考虑先卖后接回。"
        invalid = "如果放量突破或板块重新转强，取消先卖后接回。"
    else:
        execution = "先观察，不为了做T而做T。"
        invalid = "条件没有继续靠近时保持观望。"
    return {
        "plain_action_text": f"接近{direction}机会",
        "plain_action_reason": reason or f"{direction}条件接近，但还没有达到可执行标准。",
        "plain_execution_text": execution,
        "plain_invalid_condition": invalid,
    }


def _positive_t_plain_text(trade_plan: TradePlan) -> dict[str, str]:
    entry = _price_text(trade_plan.entry_price)
    exit_price = _price_text(trade_plan.exit_price)
    stop = _price_text(trade_plan.stop_loss)
    return {
        "plain_action_text": "今天可先买后卖",
        "plain_action_reason": "价格回落后重新走强，预计价差已覆盖手续费，可以先买回一部分，再卖出同等底仓。",
        "plain_execution_text": (
            f"等 {entry} 附近买入；反抽到 {exit_price} 附近卖出同等底仓。"
            f"建议仓位约 {trade_plan.position_pct:.0f}%。"
        ),
        "plain_invalid_condition": f"跌破 {stop} 或重新跌回分时均价线下方不收回，取消这次操作。",
    }


def _negative_t_plain_text(trade_plan: TradePlan) -> dict[str, str]:
    sell = _price_text(trade_plan.entry_price)
    buyback = _price_text(trade_plan.exit_price)
    stop = _price_text(trade_plan.stop_loss)
    buyback_hint = f"；{trade_plan.buyback_trigger}" if trade_plan.buyback_trigger else ""
    return {
        "plain_action_text": "今天可先卖后接回",
        "plain_action_reason": "价格冲高后开始变弱，卖出后有明确低位接回空间，可以先卖一部分，再等回落接回。",
        "plain_execution_text": (
            f"冲高到 {sell} 附近先卖；回落到 {buyback} 附近才接回，接不回不追。"
            f"建议仓位约 {trade_plan.position_pct:.0f}%{buyback_hint}"
        ),
        "plain_invalid_condition": f"重新放量突破 {stop} 或板块转强，取消先卖后接回。",
    }


def _hold_plain_text(blocking_rules: list[str]) -> dict[str, str]:
    reason = _first_blocker(blocking_rules)
    return {
        "plain_action_text": "今天别动",
        "plain_action_reason": reason or "先买后卖、先卖后接回条件都没有满足，价格位置和价差都不够确定。",
        "plain_execution_text": "不追单；等回落后重新站回分时均价线，或冲高明显变弱且有足够接回空间后再重新分析。",
        "plain_invalid_condition": "如果跌破关键支撑、放量走弱或板块退潮，继续保持观望。",
    }


def _first_blocker(blocking_rules: list[str]) -> str:
    for rule in blocking_rules:
        cleaned = str(rule).strip()
        if cleaned:
            return cleaned
    return ""


def _price_text(value: float | None) -> str:
    if value is None or value <= 0:
        return "--"
    return f"{value:.3f}"
