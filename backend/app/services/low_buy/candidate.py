from __future__ import annotations

from app.services.low_buy.candidate_metrics import build_candidate_metrics, passes_common_prefilter
from app.services.low_buy.candidate_content import (
    build_candidate_reasons,
    build_candidate_risks,
    build_candidate_tags,
    entry_tolerance_pct,
    execution_quality,
    final_position_cap,
    initial_signal_state,
)
from app.services.low_buy.exit_plan import build_exit_plan
from app.services.low_buy.hard_risk import hard_untradable_reason
from app.services.low_buy.next_day_event_model import build_next_day_event_plan
from app.services.low_buy.mainline_strength import candidate_mainline_info
from app.services.low_buy.dynamic_adjustments import (
    apply_performance_adjustment_to_candidate,
)
from app.services.low_buy.candidate_context import build_candidate_context_adjustment, merge_risk_tier
from app.services.low_buy.base_strategy import get_low_buy_strategy
from app.services.low_buy.candidate_types import CandidateContextAdjustment, CandidateMetrics, StrategySetup
from app.services.low_buy.data_quality import (
    DataQualitySnapshot,
    build_candidate_data_quality,
    build_low_buy_metrics_quality,
    combine_data_quality,
    data_quality_payload,
)
from app.services.low_buy.factor_scoring import build_factor_scores, weighted_factor_bonus
from app.services.low_buy.factor_types import FactorContext
from app.services.low_buy.positioning import build_position_breakdown_text
from app.services.low_buy.candidate_position_advice import position_advice_for_signal
from app.services.low_buy.research_layers import evaluate_research_layer, is_research_layer_strategy
from app.services.low_buy.strategy_policy import mainline_industry_allowed
from app.services.low_buy.signal_family import (
    SignalFamilyProfile,
    build_signal_family_profile,
    profile_with_setup,
)
from app.services.market.regime import MarketRegimeSnapshot
from app.services.market.state_categories import standard_market_state_payload
from app.services.low_buy.shared import (
    BoardCandidate,
    DEFAULT_PRODUCTION_LOW_BUY_STRATEGY,
    LOW_BUY_RESULT_VERSION,
    LowBuyCandidateOut,
    guess_market,
    pd,
)
from app.services.low_buy.price_math import distance_to_entry_zone_pct
from app.services.risk.volatility_sizing import build_volatility_position_cap
from app.services.quant.state_scope import reset_market_state_scope, set_market_state_scope


class LowBuyCandidateMixin:
    def _is_in_entry_zone(self, candidate: LowBuyCandidateOut) -> bool:
        return candidate.entry_zone_low <= candidate.latest_price <= candidate.entry_zone_high

    @staticmethod
    def _distance_to_entry_zone_pct(candidate: LowBuyCandidateOut, latest_price: float) -> float:
        return distance_to_entry_zone_pct(candidate, latest_price)

    def _signal_rank(self, state: str) -> int:
        ranks = {"buy_now": 5, "soft_buy_now": 4, "near_entry": 3, "watch": 2, "avoid": 1}
        return ranks.get(state, 0)

    @staticmethod
    def _get_entry_tolerance_pct(strategy: str) -> float:
        return entry_tolerance_pct(strategy)

    @staticmethod
    def _position_advice_for_signal(candidate: LowBuyCandidateOut, state: str, performance=None) -> tuple[float, str]:
        return position_advice_for_signal(candidate, state, performance)

    @staticmethod
    def _execution_quality(candidate: LowBuyCandidateOut) -> tuple[float, str]:
        return execution_quality(candidate)

    def _apply_candidate_positioning(
        self,
        candidate: LowBuyCandidateOut,
        performance=None,
    ) -> LowBuyCandidateOut:
        adjusted_candidate = (
            apply_performance_adjustment_to_candidate(candidate, performance)
            if performance is not None
            else candidate
        )
        suggested_position_pct, suggested_position_text = self._position_advice_for_signal(
            adjusted_candidate,
            adjusted_candidate.buy_signal_state,
            performance,
        )
        final_cap_pct, cap_reason = final_position_cap(
            suggested_position_pct=suggested_position_pct,
            volatility_position_pct=adjusted_candidate.volatility_position_pct,
            existing_reason=adjusted_candidate.position_cap_reason,
        )
        return adjusted_candidate.model_copy(
            update={
                "entry_distance_pct": self._distance_to_entry_zone_pct(
                    adjusted_candidate,
                    adjusted_candidate.latest_price,
                ),
                "suggested_position_pct": suggested_position_pct,
                "suggested_position_text": suggested_position_text,
                "final_position_cap_pct": final_cap_pct,
                "position_cap_reason": cap_reason,
                "position_breakdown_text": build_position_breakdown_text(
                    adjusted_candidate,
                    suggested_position_pct,
                ),
            }
        )

    def _evaluate_candidate(
        self,
        item: BoardCandidate,
        latest_trade_date: str,
        history: pd.DataFrame | None = None,
        strategy: str = DEFAULT_PRODUCTION_LOW_BUY_STRATEGY,
        hot_industries: list[str] | None = None,
        market_regime: MarketRegimeSnapshot | None = None,
        factor_context: FactorContext | None = None,
    ) -> LowBuyCandidateOut | None:
        scope_token = set_market_state_scope(market_regime.state if market_regime is not None else "")
        try:
            return self._evaluate_candidate_inner(
                item=item,
                latest_trade_date=latest_trade_date,
                history=history,
                strategy=strategy,
                hot_industries=hot_industries,
                market_regime=market_regime,
                factor_context=factor_context,
            )
        finally:
            reset_market_state_scope(scope_token)

    def _evaluate_candidate_inner(
        self,
        item: BoardCandidate,
        latest_trade_date: str,
        history: pd.DataFrame | None = None,
        strategy: str = DEFAULT_PRODUCTION_LOW_BUY_STRATEGY,
        hot_industries: list[str] | None = None,
        market_regime: MarketRegimeSnapshot | None = None,
        factor_context: FactorContext | None = None,
    ) -> LowBuyCandidateOut | None:
        hot_industries = hot_industries or []
        strategy_adapter = get_low_buy_strategy(strategy)
        if not self._passes_candidate_filters(item):
            return None
        if not mainline_industry_allowed(strategy, item.industry, hot_industries):
            return None

        metrics = self._build_candidate_metrics(item=item, latest_trade_date=latest_trade_date, history=history)
        if metrics is None or not self._passes_common_prefilter(item=item, metrics=metrics, strategy=strategy):
            return None
        metrics_quality = build_low_buy_metrics_quality(metrics)
        if metrics_quality.quality == "unavailable":
            return None
        if hard_untradable_reason(item=item, metrics=metrics)[0]:
            return None

        if not strategy_adapter.passes_prefilter(item=item, metrics=metrics):
            return None

        base_score = strategy_adapter.score_candidate(
            item=item,
            metrics=metrics,
            hot_industries=hot_industries,
        )
        signal_profile = build_signal_family_profile(
            strategy=strategy,
            item=item,
            metrics=metrics,
            hot_industries=hot_industries,
        )
        factor_scores = self._factor_scores(metrics, factor_context)
        context_adjustment = self._build_context_adjustment(
            strategy=strategy,
            item=item,
            metrics=metrics,
            hot_industries=hot_industries,
            market_regime=market_regime,
            signal_profile=signal_profile,
            factor_scores=factor_scores,
            metrics_quality=metrics_quality,
        )
        factor_bonus = self._weighted_factor_bonus(factor_scores)
        adjusted_score = max(
            0.0,
            round(base_score + signal_profile.score_bonus + factor_bonus - context_adjustment.score_penalty, 1),
        )
        score_floor = 70.0 if is_research_layer_strategy(strategy) else 74.0
        if adjusted_score < score_floor + context_adjustment.score_floor_shift:
            return None

        setup = strategy_adapter.build_setup(item=item, metrics=metrics, score=adjusted_score)
        signal_profile = profile_with_setup(signal_profile, setup, strategy=strategy)
        return self._build_candidate_output(
            strategy=strategy,
            item=item,
            metrics=metrics,
            score=adjusted_score,
            setup=setup,
            hot_industries=hot_industries,
            context_adjustment=context_adjustment,
            signal_profile=signal_profile,
            factor_scores=factor_scores,
            metrics_quality=metrics_quality,
        )

    def _passes_candidate_filters(
        self,
        item: BoardCandidate,
    ) -> bool:
        return not self._is_excluded_symbol(item.symbol, item.name)

    @staticmethod
    def _factor_scores(metrics: CandidateMetrics, context: FactorContext | None = None) -> dict[str, float]:
        return build_factor_scores(metrics, context)

    @staticmethod
    def _weighted_factor_bonus(factor_scores: dict[str, float]) -> float:
        return weighted_factor_bonus(factor_scores)

    def _build_context_adjustment(
        self,
        strategy: str,
        item: BoardCandidate,
        metrics: CandidateMetrics,
        hot_industries: list[str],
        market_regime: MarketRegimeSnapshot | None,
        signal_profile: SignalFamilyProfile,
        factor_scores: dict[str, float],
        metrics_quality: DataQualitySnapshot | None = None,
    ) -> CandidateContextAdjustment:
        return build_candidate_context_adjustment(
            strategy=strategy,
            item=item,
            metrics=metrics,
            hot_industries=hot_industries,
            market_regime=market_regime,
            signal_profile=signal_profile,
            factor_scores=factor_scores,
            metrics_quality=metrics_quality,
        )

    @staticmethod
    def _merge_risk_tier(base_tier: str, hard_risk_level: str) -> str:
        return merge_risk_tier(base_tier, hard_risk_level)

    def _build_candidate_metrics(
        self,
        item: BoardCandidate,
        latest_trade_date: str,
        history: pd.DataFrame | None,
    ) -> CandidateMetrics | None:
        return build_candidate_metrics(
            item=item,
            latest_trade_date=latest_trade_date,
            history=history,
        )

    def _passes_common_prefilter(
        self,
        item: BoardCandidate,
        metrics: CandidateMetrics,
        strategy: str = DEFAULT_PRODUCTION_LOW_BUY_STRATEGY,
    ) -> bool:
        return passes_common_prefilter(item=item, metrics=metrics, strategy=strategy)

    def _build_candidate_output(
        self,
        strategy: str,
        item: BoardCandidate,
        metrics: CandidateMetrics,
        score: float,
        setup: StrategySetup,
        hot_industries: list[str],
        context_adjustment: CandidateContextAdjustment,
        signal_profile: SignalFamilyProfile,
        factor_scores: dict[str, float],
        metrics_quality: DataQualitySnapshot | None = None,
    ) -> LowBuyCandidateOut:
        if strategy == "first_board":
            stop_anchor = min(metrics.ma10, metrics.recent_low_guard, metrics.board_low)
        elif strategy == "divergence_consensus":
            stop_anchor = metrics.consolidation_low
        else:
            stop_anchor = min(metrics.ma10, metrics.recent_low_guard)
        stop_loss = round(stop_anchor * 0.988, 3)
        take_profit = round(max(metrics.board_high, metrics.recent_swing_high) * 1.01, 3)
        exit_plan = build_exit_plan(
            strategy=strategy,
            metrics=metrics,
            setup=setup,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )
        research_layer = evaluate_research_layer(strategy, item, metrics)
        next_day_event_plan = build_next_day_event_plan(
            strategy=strategy,
            item=item,
            metrics=metrics,
            research_stage=research_layer.stage,
        )
        execution_ready = setup.execution_ready and not context_adjustment.execution_blocked
        staged_state = initial_signal_state(
            execution_blocked=context_adjustment.execution_blocked,
            execution_ready=execution_ready,
            score=score,
            research_stage=research_layer.stage,
        )
        mainline_info = candidate_mainline_info(
            sector_name=item.industry,
            mainline_industries=hot_industries,
            leader_rank=signal_profile.leader_rank,
        )
        market_state_fields = standard_market_state_payload(context_adjustment.market_state)
        quote_quality = build_candidate_data_quality(
            latest_price=metrics.latest_close,
            quote_timestamp=metrics.latest_trade_date,
        )
        quality_fields = data_quality_payload(combine_data_quality(quote_quality, metrics_quality))
        atr_pct = (metrics.atr14 / max(metrics.latest_close, 0.01) * 100) if metrics.latest_close > 0 else 0.0
        volatility_cap = build_volatility_position_cap(atr_pct)
        candidate = LowBuyCandidateOut(
            strategy_key=strategy,
            strategy_title=self._get_playbook(strategy)["title"],
            payload_version=LOW_BUY_RESULT_VERSION,
            symbol=item.symbol,
            name=item.name,
            market=guess_market(item.symbol),
            instrument_type="stock",
            sector_name=item.industry or None,
            latest_price=round(metrics.latest_close, 3),
            change_pct=round(metrics.latest_change_pct, 3),
            quote_timestamp=metrics.latest_trade_date,
            **quality_fields,
            board_date=item.board_date,
            board_count=item.board_count,
            retracement_days=metrics.retracement_days,
            score=score,
            entry_zone_low=setup.entry_zone_low,
            entry_zone_high=setup.entry_zone_high,
            stop_loss=stop_loss,
            take_profit=take_profit,
            ma5=round(metrics.ma5, 3),
            ma10=round(metrics.ma10, 3),
            ma20=round(metrics.ma20, 3),
            volume_burst_ratio=round(metrics.volume_burst_ratio, 2),
            volume_shrink_ratio=round(metrics.post_volume_ratio, 2),
            support_distance_pct=round(metrics.support_distance_pct, 2),
            distribution_risk_score=metrics.distribution_risk_score,
            trend_fatigue_score=metrics.trend_fatigue_score,
            false_breakout_flag=metrics.false_breakout_flag,
            stall_after_volume_flag=metrics.stall_after_volume_flag,
            intraday_reversal_flag=metrics.intraday_reversal_flag,
            execution_ready=execution_ready,
            execution_note=setup.execution_note,
            stage_scores=signal_profile.stage_scores,
            factor_scores=factor_scores,
            stage_text=signal_profile.stage_text,
            risk_tier=context_adjustment.risk_tier,
            trigger_condition=signal_profile.trigger_condition,
            invalid_condition=signal_profile.invalid_condition,
            next_watch_price=signal_profile.next_watch_price,
            leader_rank=signal_profile.leader_rank,
            mainline_rank=mainline_info.rank,
            mainline_tier=mainline_info.tier,
            mainline_tier_text=mainline_info.tier_text,
            dynamic_threshold_adjustment=context_adjustment.score_floor_shift,
            dynamic_position_multiplier=context_adjustment.dynamic_position_multiplier,
            risk_position_multiplier=context_adjustment.risk_position_multiplier,
            industry_tier=context_adjustment.industry_tier,
            industry_tier_text=context_adjustment.industry_tier_text,
            industry_position_multiplier=context_adjustment.industry_position_multiplier,
            atr_pct=volatility_cap.atr_pct,
            atr_window=metrics.atr_window,
            atr_source=metrics.atr_source,
            volatility_position_pct=volatility_cap.cap_pct,
            final_position_cap_pct=volatility_cap.cap_pct,
            position_cap_reason=volatility_cap.reason,
            hard_risk=context_adjustment.hard_risk,
            next_day_event_plan=next_day_event_plan,
            exit_plan=exit_plan,
            entry_distance_pct=0.0,
            suggested_position_pct=0.0,
            suggested_position_text="",
            market_state=context_adjustment.market_state,
            market_state_text=context_adjustment.market_state_text,
            market_state_category=market_state_fields["market_state_category"],
            market_state_category_text=market_state_fields["market_state_category_text"],
            market_state_strength=context_adjustment.market_state_strength,
            market_position_multiplier=context_adjustment.market_position_multiplier,
            confirmed_trade_date=metrics.latest_trade_date if execution_ready else None,
            summary_reason=setup.summary_reason,
            buy_signal_state=staged_state,
            buy_signal_text="继续观察" if staged_state == "watch" else "暂不跟踪",
            buy_signal_hint=(
                "价格未进入买点区前不追高。"
                if staged_state == "watch"
                else "结构还不够完整，先不要接。"
            ),
            research_stage=research_layer.stage,
            research_stage_text=research_layer.stage_text,
            research_failed_rules=research_layer.failed_rules,
            research_near_miss_rules=research_layer.near_miss_rules,
            research_blocked_reason=research_layer.blocked_reason,
            reasons=build_candidate_reasons(setup.reasons, research_layer),
            risks=build_candidate_risks(strategy, metrics, context_adjustment),
            tags=build_candidate_tags(
                strategy=strategy,
                item=item,
                metrics=metrics,
                hot_industries=hot_industries,
                context_adjustment=context_adjustment,
                factor_scores=factor_scores,
            ),
        )
        positioned = self._apply_candidate_positioning(candidate)
        execution_quality_score, execution_quality_text = self._execution_quality(positioned)
        return positioned.model_copy(
            update={
                "execution_quality_score": execution_quality_score,
                "execution_quality_text": execution_quality_text,
            }
        )
