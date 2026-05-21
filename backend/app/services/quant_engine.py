from __future__ import annotations

from typing import Any

from app.models.schemas import (
    AnalysisRequest,
    KlineBar,
    MarketEventOut,
    MicrostructureSnapshot,
    QuoteSnapshot,
    SectorSnapshot,
    StrategySuggestion,
    TradingRuleOut,
)
from app.services.distribution_signals import build_intraday_distribution_snapshot
from app.services.market.regime import MarketRegimeSnapshot
from app.services.indicators import (
    atr,
    closes_from_bars,
    intraday_amplitude,
    macd_with_validity,
    moving_average,
    obv,
    rsi,
    trend_slope,
    volume_ratio,
    vwap,
)
from app.services.quant_engine_blocking import hard_blocking_rules
from app.services.quant_engine_common import calc_tradability, detect_scenario, event_penalty
from app.services.quant_engine_intraday_structure import classify_intraday_structure
from app.services.quant_engine_indicator_cache import get_or_compute_indicator_snapshot, indicator_cache_key
from app.services.quant_engine_decision import (
    apply_direction_gate,
    apply_position_constraints,
    apply_trade_scene_gate,
    resolve_initial_action,
    resolve_prepare_action,
    resolve_trade_plan,
)
from app.services.quant_engine_models import IndicatorSnapshot, ScoreSnapshot, TradePlan
from app.services.quant_engine_output import (
    build_assumptions,
    build_compliance_notes,
    build_metrics,
    build_suggestion,
    empty_trade_plan,
)
from app.services.quant_engine_scoring import (
    action_thresholds,
    build_reasons,
    negative_score,
    positive_score,
    risk_level,
    risk_score,
)
from app.services.quant_engine_scenes import resolve_trade_scene


class QuantEngine:
    def evaluate(
        self,
        quote: QuoteSnapshot,
        bars: list[KlineBar],
        rules: TradingRuleOut,
        sector: SectorSnapshot,
        events: list[MarketEventOut],
        microstructure: MicrostructureSnapshot,
        request: AnalysisRequest,
        risk_config: dict[str, Any],
        market_regime: MarketRegimeSnapshot | None = None,
    ) -> tuple[dict[str, Any], StrategySuggestion, list[str], list[str]]:
        indicators = self._collect_indicators(quote=quote, bars=bars)
        scores = self._score_market_context(
            quote=quote,
            indicators=indicators,
            sector=sector,
            events=events,
            microstructure=microstructure,
            risk_config=risk_config,
            market_regime=market_regime,
        )
        assumptions = build_assumptions(request.base_position, request.available_position)
        if not indicators.macd_valid:
            assumptions.append("MACD 样本不足，本次不把 0 轴状态作为有效多空信号。")
        blocking_rules = self._initial_blocking_rules(
            quote=quote,
            indicators=indicators,
            scores=scores,
            request=request,
            rules=rules,
            risk_config=risk_config,
        )
        trade_scene = resolve_trade_scene(
            quote=quote,
            indicators=indicators,
            sector=sector,
            microstructure=microstructure,
            market_regime=market_regime,
        )
        action = resolve_initial_action(request=request, scores=scores, blocking_rules=blocking_rules)
        if action == "hold":
            action = resolve_prepare_action(request=request, scores=scores, blocking_rules=blocking_rules)
        action, blocking_rules = apply_trade_scene_gate(
            action=action,
            scores=scores,
            trade_scene=trade_scene,
            blocking_rules=blocking_rules,
        )
        action, blocking_rules = apply_position_constraints(
            action=action,
            request=request,
            rules=rules,
            blocking_rules=blocking_rules,
        )
        action, blocking_rules, signal_layer, near_action, layer_reason = apply_direction_gate(
            action=action,
            quote=quote,
            indicators=indicators,
            sector=sector,
            microstructure=microstructure,
            blocking_rules=blocking_rules,
            market_regime=market_regime,
        )
        trade_plan, blocking_rules = resolve_trade_plan(
            action=action,
            request=request,
            quote=quote,
            indicators=indicators,
            scores=scores,
            risk_config=risk_config,
            blocking_rules=blocking_rules,
            market_regime=market_regime,
            trade_scene=trade_scene,
            sector=sector,
            signal_layer=signal_layer,
            near_action=near_action,
            layer_reason=layer_reason,
        )
        reasons = build_reasons(
            action=trade_plan.action,
            market_regime=market_regime,
            positive_score_value=scores.positive_score,
            negative_score_value=scores.negative_score,
            ma5=indicators.ma5,
            ma20=indicators.ma20,
            rsi14=indicators.rsi14,
            macd_hist=indicators.macd_hist,
            vwap_value=indicators.vwap_value,
            sector=sector,
            microstructure=microstructure,
            scenario=scores.scenario,
            distribution=indicators.distribution,
        )
        reasons.insert(1, f"做T场景：{trade_scene.label}。{trade_scene.reason}")
        compliance_notes = build_compliance_notes(
            quote=quote,
            trade_plan=trade_plan,
            scores=scores,
            market_regime=market_regime,
        )
        metrics = build_metrics(
            quote=quote,
            indicators=indicators,
            scores=scores,
            trade_plan=trade_plan,
            risk_config=risk_config,
            market_regime=market_regime,
        )
        suggestion = build_suggestion(
            action=trade_plan.action,
            trade_plan=trade_plan,
            scores=scores,
            reasons=reasons,
            blocking_rules=blocking_rules,
            rules=rules,
        )
        return metrics, suggestion, compliance_notes, assumptions

    def _collect_indicators(self, quote: QuoteSnapshot, bars: list[KlineBar]) -> IndicatorSnapshot:
        return get_or_compute_indicator_snapshot(
            indicator_cache_key(quote, bars),
            lambda: self._compute_indicators(quote=quote, bars=bars),
        )

    def _compute_indicators(self, quote: QuoteSnapshot, bars: list[KlineBar]) -> IndicatorSnapshot:
        closes = closes_from_bars(bars)
        macd_dif, macd_dea, macd_hist, macd_valid = macd_with_validity(closes)
        vwap_value = vwap(bars)
        ma5 = moving_average(closes, 5)
        ma20 = moving_average(closes, 20)
        ma60 = moving_average(closes, 60)
        distribution = build_intraday_distribution_snapshot(
            bars=bars,
            quote=quote,
            vwap_value=vwap_value,
        )
        intraday_structure = classify_intraday_structure(
            quote=quote,
            bars=bars,
            ma5=ma5,
            vwap_value=vwap_value,
            distribution=distribution,
        )
        return IndicatorSnapshot(
            ma5=ma5,
            ma20=ma20,
            ma60=ma60,
            rsi14=rsi(closes, 14),
            macd_dif=macd_dif,
            macd_dea=macd_dea,
            macd_hist=macd_hist,
            macd_valid=macd_valid,
            vwap_value=vwap_value,
            atr14=atr(bars, 14) or 0.0,
            volume_ratio_value=quote.volume_ratio or volume_ratio(bars, 20),
            amplitude=intraday_amplitude(bars, prev_close=quote.prev_close),
            slope10=trend_slope(closes, 10),
            obv_value=obv(bars),
            distribution=distribution,
            latest_bar=bars[-1] if bars else None,
            intraday_structure=intraday_structure.key,
            intraday_structure_text=intraday_structure.text,
        )

    def _score_market_context(
        self,
        quote: QuoteSnapshot,
        indicators: IndicatorSnapshot,
        sector: SectorSnapshot,
        events: list[MarketEventOut],
        microstructure: MicrostructureSnapshot,
        risk_config: dict[str, Any],
        market_regime: MarketRegimeSnapshot | None,
        ) -> ScoreSnapshot:
        tradability_score = calc_tradability(
            quote,
            indicators.amplitude,
            indicators.volume_ratio_value,
            indicators.atr14,
        )
        event_penalty_value = event_penalty(events)
        scenario = detect_scenario(
            quote.timestamp or (indicators.latest_bar.timestamp if indicators.latest_bar else ""),
            risk_config,
        )
        macd_hist_for_score = indicators.macd_hist if indicators.macd_valid else float("nan")
        positive_score_value = positive_score(
            quote,
            indicators.ma5,
            indicators.ma20,
            indicators.ma60,
            indicators.rsi14,
            macd_hist_for_score,
            indicators.vwap_value,
            sector,
            microstructure,
            indicators.slope10,
            indicators.distribution,
        )
        negative_score_value = negative_score(
            quote,
            indicators.ma5,
            indicators.rsi14,
            macd_hist_for_score,
            indicators.vwap_value,
            sector,
            microstructure,
            indicators.amplitude,
            indicators.distribution,
        )
        risk_score_value = risk_score(
            amplitude=indicators.amplitude,
            atr_value=indicators.atr14,
            tradability_score=tradability_score,
            sector=sector,
            events=events,
        )
        risk_level_value = risk_level(risk_score_value)
        positive_threshold, negative_threshold = action_thresholds(
            scenario,
            risk_level_value,
            market_regime=market_regime,
        )
        return ScoreSnapshot(
            tradability_score=tradability_score,
            event_penalty=event_penalty_value,
            scenario=scenario,
            market_state=market_regime.state if market_regime else "low_volume_wait",
            market_state_text=market_regime.label if market_regime else "缩量无主线",
            market_bonus=market_regime.ranking_bonus if market_regime else 0.0,
            positive_score=positive_score_value,
            negative_score=negative_score_value,
            signal_score=max(positive_score_value, negative_score_value) - event_penalty_value,
            risk_score=risk_score_value,
            risk_level=risk_level_value,
            positive_threshold=positive_threshold,
            negative_threshold=negative_threshold,
        )

    def _initial_blocking_rules(
        self,
        quote: QuoteSnapshot,
        indicators: IndicatorSnapshot,
        scores: ScoreSnapshot,
        request: AnalysisRequest,
        rules: TradingRuleOut,
        risk_config: dict[str, Any],
    ) -> list[str]:
        blocking_rules = hard_blocking_rules(
            quote=quote,
            amplitude=indicators.amplitude,
            atr_value=indicators.atr14,
            tradability_score=scores.tradability_score,
            event_penalty_value=scores.event_penalty,
            scenario=scores.scenario,
            has_latest_bar=bool(indicators.latest_bar),
            risk_config=risk_config,
        )
        if request.base_position <= 0 and rules.requires_base_position:
            blocking_rules.append("当前标的需要底仓做T，但未提供底仓数量。")
        if request.available_position <= 0:
            blocking_rules.append("当前可卖数量为 0，卖出型交易无法执行。")
        return blocking_rules
