from __future__ import annotations

from app.services.low_buy.candidate_metrics import build_candidate_metrics, passes_common_prefilter
from app.services.low_buy.exit_plan import build_exit_plan
from app.services.low_buy.hard_risk import build_hard_risk_assessment
from app.services.low_buy.market_state_rules import (
    build_low_buy_market_adjustment,
)
from app.services.low_buy.next_day_event_model import build_next_day_event_plan
from app.services.low_buy.industry_positioning import build_industry_position_adjustment
from app.services.low_buy.mainline_strength import candidate_mainline_info
from app.services.low_buy.dynamic_adjustments import (
    apply_performance_adjustment_to_candidate,
    low_buy_dynamic_adjustment,
)
from app.services.low_buy.base_strategy import get_low_buy_strategy
from app.services.low_buy.candidate_types import CandidateContextAdjustment, CandidateMetrics, StrategySetup
from app.services.low_buy.data_quality import build_candidate_data_quality, data_quality_payload
from app.services.low_buy.factor_scoring import build_factor_scores, weighted_factor_bonus
from app.services.low_buy.factor_types import FactorContext
from app.services.low_buy.positioning import build_position_breakdown_text
from app.services.low_buy.candidate_position_advice import position_advice_for_signal
from app.services.low_buy.research_layers import evaluate_research_layer, is_research_layer_strategy
from app.services.low_buy.risk_tiers import resolve_low_buy_risk_tier
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
        tolerance_map = {
            "classic_retrace": 0.8,
            "ma_support": 0.8,
            "first_board": 0.6,
            "volume_shrink": 0.6,
            "late_session_strong_support": 0.4,
            "core_midcap_vwap_ma5_retrace": 0.6,
            "sector_mainline_first_divergence_low_buy": 0.6,
            "breakout_support": 0.5,
            "limit_up_breakout_retrace": 0.35,
            "divergence_consensus": 0.25,
            "deep_pullback": 0.0,
            "trend_rebound": 0.6,
        }
        return tolerance_map.get(strategy, 0.5)

    @staticmethod
    def _position_advice_for_signal(candidate: LowBuyCandidateOut, state: str, performance=None) -> tuple[float, str]:
        return position_advice_for_signal(candidate, state, performance)

    @staticmethod
    def _execution_quality(candidate: LowBuyCandidateOut) -> tuple[float, str]:
        state_score = {
            "buy_now": 34.0,
            "soft_buy_now": 27.0,
            "near_entry": 20.0,
            "watch": 8.0,
            "avoid": -22.0,
        }.get(candidate.buy_signal_state, 0.0)
        distance = max(candidate.entry_distance_pct, 0.0)
        if distance <= 0:
            distance_score = 18.0
        elif distance <= 0.5:
            distance_score = 12.0
        elif distance <= 1.0:
            distance_score = 7.0
        elif distance <= 2.0:
            distance_score = 2.0
        else:
            distance_score = -min(18.0, distance * 3.0)
        stop_gap = (
            (candidate.latest_price - candidate.stop_loss) / max(candidate.latest_price, 0.01) * 100
            if candidate.latest_price > 0
            else 0.0
        )
        if candidate.stop_loss >= candidate.latest_price:
            risk_score = -24.0
        elif 2.0 <= stop_gap <= 9.0:
            risk_score = 10.0
        elif stop_gap > 14.0:
            risk_score = -5.0
        else:
            risk_score = 3.0
        tier_score = {"block": -28.0, "degrade": -10.0, "note": 3.0}.get(candidate.risk_tier, 0.0)
        distribution_penalty = min(max(candidate.distribution_risk_score - 3.5, 0.0) * 2.6, 12.0)
        raw_score = 42.0 + state_score + distance_score + risk_score + tier_score - distribution_penalty
        score = round(max(0.0, min(raw_score, 100.0)), 1)
        if candidate.risk_tier == "block" or candidate.buy_signal_state == "avoid":
            label = "禁入"
        elif score >= 78:
            label = "高"
        elif score >= 58:
            label = "中"
        else:
            label = "低"
        return score, f"执行质量：{label}，到价/止跌/风控综合评分 {score:.1f}"

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
        return adjusted_candidate.model_copy(
            update={
                "entry_distance_pct": self._distance_to_entry_zone_pct(
                    adjusted_candidate,
                    adjusted_candidate.latest_price,
                ),
                "suggested_position_pct": suggested_position_pct,
                "suggested_position_text": suggested_position_text,
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
        hot_industries = hot_industries or []
        strategy_adapter = get_low_buy_strategy(strategy)
        if not self._passes_candidate_filters(item):
            return None
        if not mainline_industry_allowed(strategy, item.industry, hot_industries):
            return None

        metrics = self._build_candidate_metrics(item=item, latest_trade_date=latest_trade_date, history=history)
        if metrics is None or not self._passes_common_prefilter(item=item, metrics=metrics, strategy=strategy):
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
    ) -> CandidateContextAdjustment:
        score_penalty = 0.0
        execution_blocked = False
        extra_risks: list[str] = []
        extra_tags: list[str] = []
        market_state_strength = 0.0

        if hot_industries and item.industry and item.industry not in hot_industries:
            score_penalty += 1.6
            extra_tags.append("非热点行业")
            extra_risks.append("当前不在强主线行业内，持续性通常弱于热点龙头。")
        risk_decision = resolve_low_buy_risk_tier(
            strategy=strategy,
            metrics=metrics,
            market_regime=market_regime,
        )
        hard_risk = build_hard_risk_assessment(item=item, metrics=metrics)
        score_penalty += hard_risk.score_penalty
        execution_blocked = execution_blocked or hard_risk.execution_blocked
        extra_risks.extend(hard_risk.reasons)
        extra_tags.extend(hard_risk.tags)
        score_penalty += risk_decision.score_penalty
        execution_blocked = execution_blocked or risk_decision.execution_blocked
        extra_risks.extend(risk_decision.risks)
        extra_tags.extend(risk_decision.tags)

        market_state = market_regime.state if market_regime is not None else "low_volume_wait"
        market_state_text = market_regime.label if market_regime is not None else "缩量观望"
        dynamic_adjustment = low_buy_dynamic_adjustment(
            market_regime=market_regime,
            risk_tier=risk_decision.risk_tier,
            leader_rank=signal_profile.leader_rank,
            factor_bonuses=factor_scores,
        )
        market_adjustment = build_low_buy_market_adjustment(
            strategy=strategy,
            market_state=market_state,
            market_state_text=market_state_text,
            market_state_strength=market_regime.state_strength if market_regime is not None else 0.0,
        )
        industry_adjustment = build_industry_position_adjustment(
            sector_name=item.industry,
            hot_industries=hot_industries,
            leader_rank=signal_profile.leader_rank,
            market_state=market_state,
            market_state_strength=market_regime.state_strength if market_regime is not None else 0.0,
        )
        score_penalty += market_adjustment.score_penalty * market_adjustment.candidate_penalty_weight
        market_state_strength = market_adjustment.market_state_strength
        extra_risks.extend(market_adjustment.extra_risks)
        extra_tags.extend(
            [
                *market_adjustment.extra_tags,
                dynamic_adjustment.reason,
                industry_adjustment.label,
            ]
        )

        risk_tier = self._merge_risk_tier(risk_decision.risk_tier, hard_risk.level)
        return CandidateContextAdjustment(
            score_penalty=score_penalty,
            score_floor_shift=dynamic_adjustment.score_floor_shift,
            soft_buy_threshold_shift=dynamic_adjustment.soft_buy_threshold_shift,
            candidate_penalty_weight=market_adjustment.candidate_penalty_weight,
            market_position_multiplier=round(max(0.0, min(1.2, market_adjustment.position_multiplier)), 4),
            risk_position_multiplier=round(max(0.0, min(1.0, risk_decision.position_multiplier)), 4),
            dynamic_position_multiplier=dynamic_adjustment.position_multiplier,
            industry_tier=industry_adjustment.tier,
            industry_tier_text=industry_adjustment.label,
            industry_position_multiplier=industry_adjustment.multiplier,
            execution_blocked=execution_blocked,
            risk_tier=risk_tier,
            dynamic_adjustment_reason=dynamic_adjustment.reason,
            market_state=market_state,
            market_state_text=market_state_text,
            market_state_strength=market_state_strength,
            hard_risk=hard_risk,
            extra_risks=extra_risks,
            extra_tags=extra_tags,
        )

    @staticmethod
    def _merge_risk_tier(base_tier: str, hard_risk_level: str) -> str:
        order = {"note": 0, "degrade": 1, "block": 2}
        hard_tier = "block" if hard_risk_level == "block" else ("degrade" if hard_risk_level == "degrade" else "note")
        return hard_tier if order[hard_tier] > order.get(base_tier, 0) else base_tier

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
        staged_state = self._initial_signal_state(
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
        quality_fields = data_quality_payload(
            build_candidate_data_quality(
                latest_price=metrics.latest_close,
                quote_timestamp=metrics.latest_trade_date,
            )
        )
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
            reasons=self._build_candidate_reasons(setup.reasons, research_layer),
            risks=self._build_candidate_risks(strategy, metrics, context_adjustment),
            tags=self._build_candidate_tags(
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

    @staticmethod
    def _initial_signal_state(
        *,
        execution_blocked: bool,
        execution_ready: bool,
        score: float,
        research_stage: str,
    ) -> str:
        if research_stage == "blocked":
            return "avoid"
        if research_stage in {"watch", "near_entry", "buy_ready"}:
            return "watch"
        if execution_blocked:
            return "avoid"
        return "watch" if execution_ready or score >= 80 else "avoid"

    @staticmethod
    def _build_candidate_reasons(base_reasons: list[str], research_layer) -> list[str]:
        reasons = list(base_reasons)
        if research_layer.stage in {"watch", "near_entry", "buy_ready"} and research_layer.stage_text:
            reasons.append(f"研究分层：{research_layer.stage_text}。")
        if research_layer.near_miss_rules:
            reasons.extend(research_layer.near_miss_rules[:2])
        if research_layer.failed_rules:
            reasons.append("仍缺确认：" + "；".join(research_layer.failed_rules[:3]) + "。")
        if research_layer.blocked_reason:
            reasons.append(research_layer.blocked_reason)
        return reasons

    def _build_candidate_risks(
        self,
        strategy: str,
        metrics: CandidateMetrics,
        context_adjustment: CandidateContextAdjustment,
    ) -> list[str]:
        if strategy == "limit_up_breakout_retrace":
            risks = [
                "跌回平台高点、涨停开盘价或涨停低点，说明突破回踩失败。",
                "这类策略只适合低位平台突破后的首轮回踩，不适合追高加速段。",
            ]
            if metrics.false_breakout_flag:
                risks.append("突破后重新跌回关键位，疑似假突破，本轮不执行。")
            if metrics.intraday_reversal_flag:
                risks.append("回踩后冲高回落，说明承接不足，需要重新确认。")
            if metrics.distribution_risk_score >= 5.0:
                risks.append("派发风险偏高，回踩确认需要降级观察。")
            if context_adjustment.execution_blocked:
                risks.append("市场或风险分层阻断强买，只保留观察提醒。")
            return risks + context_adjustment.extra_risks
        if strategy == "divergence_consensus":
            risks = [
                "跌回分歧高点或横盘下沿，说明突破失败，应直接放弃。",
                "这类策略是右侧确认，不适合在缩量弱市或高位退潮期追击。",
            ]
            if metrics.false_breakout_flag:
                risks.append("突破后重新跌回关键位，疑似假突破，本轮不执行。")
            if metrics.stall_after_volume_flag:
                risks.append("放量后价格扩张变差，可能是边拉边派发。")
            if metrics.intraday_reversal_flag:
                risks.append("突破日冲高回落，收盘承接不足，需要重新站稳。")
            if metrics.distribution_risk_score >= 5.0:
                risks.append("派发风险偏高，突破确认需要降级观察。")
            if context_adjustment.execution_blocked:
                risks.append("风险分层已触发执行阻断，本轮不允许进入确定买入。")
            return risks + context_adjustment.extra_risks
        risks = [
            "跌破止损位说明本次低吸逻辑失效，应直接离场。",
            "只适合上升趋势或震荡偏强市场，跌停潮里应整体降级处理。",
        ]
        if not metrics.shrink_basic_ok:
            risks.append("回调量能还没基本缩到位，若继续放量下跌，应从名单中剔除。")
        elif not metrics.shrink_ok:
            risks.append("当前缩量只是基本成立，还没到最理想的干净洗盘状态。")
        if not metrics.momentum_exhaustion:
            risks.append("下跌动能尚未钝化，当前仍不能硬接。")
        if metrics.distribution_risk_score >= 6.0:
            risks.append("近期派发风险偏高，哪怕价格到位也要等更强确认。")
        if metrics.trend_fatigue_score >= 6.0:
            risks.append("近 3 日出现趋势疲劳迹象，不能只按均线多头判断强势。")
        if context_adjustment.execution_blocked:
            risks.append("风险分层已触发执行阻断，本轮不允许进入确定买入。")
        return risks + context_adjustment.extra_risks

    def _build_candidate_tags(
        self,
        strategy: str,
        item: BoardCandidate,
        metrics: CandidateMetrics,
        hot_industries: list[str],
        context_adjustment: CandidateContextAdjustment,
        factor_scores: dict[str, float],
    ) -> list[str]:
        factor_tags = [f"{label}+{value:.1f}" for label, value in _factor_score_labels(factor_scores)]
        if strategy == "limit_up_breakout_retrace":
            return [
                "热点行业" if item.industry and hot_industries and item.industry in hot_industries else "趋势筛选",
                "平台回踩",
                "缩量承接" if metrics.post_volume_ratio <= 1.05 else "缩量待确认",
                "关键位附近" if metrics.platform_support_distance_pct <= 5.0 else "未到关键位",
                "首板启动",
                "研究策略",
                self._distribution_tag(metrics.distribution_risk_score),
                f"风险层级:{context_adjustment.risk_tier}",
                *factor_tags,
                *context_adjustment.extra_tags,
            ]
        if strategy == "divergence_consensus":
            return [
                "热点行业" if item.industry and hot_industries and item.industry in hot_industries else "趋势筛选",
                "分歧突破" if metrics.consensus_breakout else "突破待确认",
                "横盘缩量" if metrics.consolidation_volume_ratio <= 0.72 else "缩量不足",
                "首板启动",
                "右侧确认",
                self._distribution_tag(metrics.distribution_risk_score),
                f"风险层级:{context_adjustment.risk_tier}",
                *factor_tags,
                *context_adjustment.extra_tags,
            ]
        return [
            "热点行业" if item.industry and hot_industries and item.industry in hot_industries else "趋势筛选",
            "缩量回调" if metrics.shrink_ok else ("缩量基本成立" if metrics.shrink_basic_ok else "缩量待确认"),
            "均线支撑" if metrics.support_ok else "靠近支撑",
            "首板优先" if item.board_count == 1 else f"{item.board_count} 连板",
            "强趋势" if metrics.strong_trend else "趋势未坏",
            "趋势疲劳" if metrics.trend_fatigue_score >= 6.0 else "趋势健康",
            self._distribution_tag(metrics.distribution_risk_score),
            f"风险层级:{context_adjustment.risk_tier}",
            *factor_tags,
            *context_adjustment.extra_tags,
        ]

    @staticmethod
    def _distribution_tag(distribution_risk_score: float) -> str:
        if distribution_risk_score >= 6.0:
            return "派发风险高"
        if distribution_risk_score >= 3.5:
            return "派发风险关注"
        return "派发风险低"


def _factor_score_labels(factor_scores: dict[str, float]) -> list[tuple[str, float]]:
    labels = {
        "deep_pullback_factor": "深回踩因子",
        "trend_rebound_factor": "龙回头因子",
        "shrink_quality_factor": "缩量质量",
        "gap_risk_factor": "缺口风险低",
        "volatility_regime_factor": "波动收敛",
        "time_efficiency_factor": "回撤节奏",
        "price_structure_factor": "价格结构",
        "sector_density_factor": "板块共振",
        "sector_flow_factor": "板块资金",
        "big_order_flow_factor": "大单流向",
        "event_risk_factor": "公告风险低",
        "signal_freshness_factor": "信号新鲜",
        "absorption_quality_factor": "分时承接",
    }
    return [
        (labels.get(key, key), value)
        for key, value in factor_scores.items()
        if value > 0
    ]
