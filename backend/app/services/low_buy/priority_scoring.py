from __future__ import annotations

from math import sqrt

from app.models.schemas import LowBuyCandidateOut, LowBuyPerformanceBucketOut, LowBuyStrategyPerformanceOut
from app.services.low_buy.market_state_rules import resolve_strategy_market_profile
from app.services.low_buy.performance_stats import retracement_bucket as resolve_retracement_bucket
from app.services.low_buy.priority_types import PriorityMarketContext, StrategyHit
from app.services.low_buy.strategy_families import family_overlap_multiplier
from app.services.low_buy.strategy_policy import get_tier_weight


class LowBuyPriorityScoringMixin:
    def _base_priority_score(self, candidate: LowBuyCandidateOut) -> float:
        state_weight = {
            "buy_now": 36.0,
            "soft_buy_now": 31.0,
            "near_entry": 24.0,
            "watch": 13.0,
            "avoid": 0.0,
        }.get(candidate.buy_signal_state, 0.0)
        entry_score = max(0.0, 20.0 - min(max(candidate.entry_distance_pct, 0.0), 10.0) * 4.0)
        risk_penalty = 10.0 if candidate.stop_loss >= candidate.latest_price else 0.0
        position_score = min(candidate.suggested_position_pct * 0.3, 9.0)
        liquidity_score = min(candidate.volume_burst_ratio * 4.0, 10.0)
        execution_score = max(-2.0, min((candidate.execution_quality_score - 55.0) * 0.08, 4.0))
        mainline_score = {
            "core_mainline": 3.0,
            "secondary_mainline": 1.8,
            "rotation_hot": 0.5,
            "non_mainline": -1.2,
        }.get(candidate.mainline_tier, 0.0)
        return (
            candidate.score
            + state_weight
            + entry_score
            + position_score
            + liquidity_score
            + execution_score
            + mainline_score
            - risk_penalty
        )

    def _final_rank_score(
        self,
        candidate: LowBuyCandidateOut,
        aggregate_weight: float,
        family_count: int,
        strategy_weight: float,
        market_context: PriorityMarketContext,
    ) -> float:
        multi_bonus = min(10.0, max(0, family_count - 1) * 2.5)
        score = self._base_priority_score(candidate)
        score += strategy_weight * 0.30 + aggregate_weight * 0.15 + multi_bonus
        score += self._environment_rank_bonus(candidate, market_context)
        return round(score, 2)

    def _single_strategy_rank(self, candidate: LowBuyCandidateOut, strategy_weight: float) -> float:
        return round(self._base_priority_score(candidate) + strategy_weight * 0.35, 2)

    def _aggregate_strategy_weight(self, hits: list[StrategyHit]) -> float:
        ordered_hits = self._ordered_hits_for_aggregation(hits)
        if not ordered_hits:
            return 0.0
        slot_multipliers = (1.0, 0.35, 0.20, 0.10)
        family_seen: dict[str, int] = {}
        aggregate = 0.0
        for index, hit in enumerate(ordered_hits[: len(slot_multipliers)]):
            family_key = hit.family_key or hit.strategy_key
            duplicate_index = family_seen.get(family_key, 0)
            effective_weight = self._hit_total_weight(hit) * family_overlap_multiplier(duplicate_index)
            aggregate += effective_weight * slot_multipliers[index]
            family_seen[family_key] = duplicate_index + 1
        return min(round(aggregate, 2), 120.0)

    def _effective_family_count(self, hits: list[StrategyHit]) -> int:
        family_keys = {hit.family_key or hit.strategy_key for hit in hits}
        return len(family_keys)

    @staticmethod
    def _effective_strategy_count(hits: list[StrategyHit]) -> int:
        return len({hit.strategy_key for hit in hits})

    def _ordered_hits_for_aggregation(self, hits: list[StrategyHit]) -> list[StrategyHit]:
        ordered_hits = sorted(
            hits,
            key=self._hit_total_weight,
            reverse=True,
        )
        primary_hits: list[StrategyHit] = []
        overflow_hits: list[StrategyHit] = []
        seen_families: set[str] = set()
        for hit in ordered_hits:
            family_key = hit.family_key or hit.strategy_key
            if family_key in seen_families:
                overflow_hits.append(hit)
                continue
            primary_hits.append(hit)
            seen_families.add(family_key)
        return primary_hits + overflow_hits

    def _strategy_weight_score(
        self,
        performance: LowBuyStrategyPerformanceOut | None,
        recent_performance: LowBuyStrategyPerformanceOut | None,
    ) -> float:
        if performance is None:
            return 46.0
        base_score = self._single_performance_score(performance)
        if recent_performance is None:
            return base_score
        recent_score = self._single_performance_score(recent_performance)
        recent_reliability = self._recent_adjustment_reliability(recent_performance.filled_signals)
        if recent_reliability <= 0:
            return base_score
        adjustment = (recent_score - base_score) * 0.35 * recent_reliability
        return round(base_score + max(min(adjustment, 10.0), -10.0), 2)

    def _single_performance_score(self, performance: LowBuyStrategyPerformanceOut) -> float:
        baseline = 40.0
        if performance.filled_signals < 20:
            return baseline
        raw = baseline
        raw += performance.hit_rate * 0.22
        raw += performance.net_win_rate * 0.08
        raw += self._normalize_range(performance.avg_net_return_pct, low=-5.0, high=8.0) * 0.10
        raw += self._normalize_range(performance.avg_return_3d, low=-5.0, high=8.0) * 0.12
        raw += self._normalize_range(performance.avg_return_5d, low=-8.0, high=12.0) * 0.10
        raw += self._normalize_range(performance.avg_max_gain_5d, low=0.0, high=18.0) * 0.08
        drawdown = abs(min(performance.avg_max_drawdown_5d, 0.0))
        raw -= self._normalize_range(drawdown, low=0.0, high=12.0) * 0.10
        raw -= min(max(performance.not_filled_rate, 0.0), 80.0) * 0.05
        raw -= min(max(performance.stop_loss_rate, 0.0), 80.0) * 0.06
        raw = min(max(raw, 22.0), 88.0)
        reliability = self._performance_reliability(performance.filled_signals)
        return round(baseline + (raw - baseline) * reliability, 2)

    def _strategy_context_bonus(
        self,
        candidate: LowBuyCandidateOut,
        performance: LowBuyStrategyPerformanceOut | None,
        recent_performance: LowBuyStrategyPerformanceOut | None,
    ) -> float:
        reference = self._select_context_performance(performance, recent_performance)
        if reference is None:
            return 0.0
        bonus = 0.0
        sector_bucket = next(
            (item for item in reference.sector_attribution if item.label == (candidate.sector_name or "未分类")),
            None,
        )
        retracement_bucket = next(
            (
                item
                for item in reference.retracement_attribution
                if item.label == resolve_retracement_bucket(candidate.retracement_days)
            ),
            None,
        )
        market_bucket = self._find_performance_bucket(
            reference.market_state_attribution,
            candidate.market_state or "low_volume_wait",
        )
        industry_bucket = self._find_performance_bucket(
            reference.industry_tier_attribution,
            candidate.industry_tier or "neutral",
        )
        if sector_bucket:
            bonus += self._bucket_bonus(sector_bucket.hit_rate, sector_bucket.avg_return_3d, sector_bucket.sample_count, cap=4.0)
        if retracement_bucket:
            bonus += self._bucket_bonus(
                retracement_bucket.hit_rate,
                retracement_bucket.avg_return_5d,
                retracement_bucket.sample_count,
                cap=4.0,
            )
        if market_bucket:
            bonus += self._bucket_context_adjustment(market_bucket, return_field="avg_return_5d", cap=2.6)
        if industry_bucket:
            bonus += self._bucket_context_adjustment(industry_bucket, return_field="avg_return_3d", cap=2.2)
        return round(max(-4.0, min(bonus, 10.0)), 2)

    @staticmethod
    def _hit_total_weight(hit: StrategyHit) -> float:
        return (hit.strategy_weight_score + hit.context_bonus) * get_tier_weight(hit.strategy_key)

    @staticmethod
    def _recent_adjustment_reliability(sample_count: int) -> float:
        if sample_count < 20:
            return 0.0
        if sample_count < 50:
            return round(0.12 + (sample_count - 20) / 30.0 * 0.28, 4)
        if sample_count < 100:
            return round(0.4 + (sample_count - 50) / 50.0 * 0.6, 4)
        return 1.0

    @staticmethod
    def _select_context_performance(
        performance: LowBuyStrategyPerformanceOut | None,
        recent_performance: LowBuyStrategyPerformanceOut | None,
    ) -> LowBuyStrategyPerformanceOut | None:
        if recent_performance is not None and recent_performance.filled_signals >= 20:
            return recent_performance
        if performance is not None and performance.filled_signals >= 20:
            return performance
        return None

    @staticmethod
    def _performance_reliability(filled_signals: int) -> float:
        if filled_signals < 20:
            return 0.0
        if filled_signals < 50:
            return round(0.18 + (filled_signals - 20) / 30.0 * 0.32, 4)
        if filled_signals < 100:
            return round(0.50 + (filled_signals - 50) / 50.0 * 0.50, 4)
        return 1.0

    def _bucket_bonus(self, hit_rate: float, avg_return: float, sample_count: int, cap: float) -> float:
        reliability = min(1.0, sqrt(max(sample_count, 0) / 6.0))
        score = self._normalize_range(hit_rate, low=35.0, high=75.0) * 0.02
        score += self._normalize_range(avg_return, low=-2.0, high=8.0) * 0.025
        return min(score * reliability, cap)

    @staticmethod
    def _find_performance_bucket(
        buckets: list[LowBuyPerformanceBucketOut],
        label: str,
    ) -> LowBuyPerformanceBucketOut | None:
        return next((item for item in buckets if item.label == label), None)

    def _bucket_context_adjustment(
        self,
        bucket: LowBuyPerformanceBucketOut,
        return_field: str,
        cap: float,
    ) -> float:
        if bucket.sample_count < 3:
            return 0.0
        reliability = min(1.0, sqrt(max(bucket.sample_count, 0) / 8.0))
        avg_return = bucket.avg_return_5d if return_field == "avg_return_5d" else bucket.avg_return_3d
        hit_score = self._normalize_signed(bucket.hit_rate, midpoint=45.0, spread=30.0)
        return_score = self._normalize_signed(avg_return, midpoint=1.5, spread=5.0)
        raw = (hit_score * 0.55 + return_score * 0.45) * cap * reliability
        return round(max(-cap * 0.65, min(cap, raw)), 2)

    def _environment_rank_bonus(
        self,
        candidate: LowBuyCandidateOut,
        market_context: PriorityMarketContext,
    ) -> float:
        market_bonus = self._market_state_bonus(candidate, market_context)
        strategy_bonus = self._strategy_rank_tilt(candidate, market_context)
        sector_bonus = self._sector_rotation_bonus(candidate, market_context)
        return round(max(-4.5, min(4.5, market_bonus + strategy_bonus + sector_bonus * 0.85)), 2)

    def _market_state_bonus(self, candidate: LowBuyCandidateOut, market_context: PriorityMarketContext) -> float:
        if candidate.buy_signal_state in {"buy_now", "soft_buy_now"}:
            multiplier = 0.55
        elif candidate.buy_signal_state == "near_entry":
            multiplier = 0.35
        else:
            multiplier = 0.20
        strength = 0.35 + market_context.market_state_strength * 0.30
        return round(market_context.market_bonus * multiplier * strength, 2)

    def _strategy_rank_tilt(
        self,
        candidate: LowBuyCandidateOut,
        market_context: PriorityMarketContext,
    ) -> float:
        profile = resolve_strategy_market_profile(
            candidate.strategy_key,
            market_context.market_state,
            market_context.market_state_strength,
        )
        return round(max(-2.0, min(2.0, profile.ranking_bonus * 0.25)), 2)

    def _sector_rotation_bonus(self, candidate: LowBuyCandidateOut, market_context: PriorityMarketContext) -> float:
        sector_name = (candidate.sector_name or "").strip()
        if not market_context.hot_industries:
            return 0.0
        source_factor = {
            "mainline_strength": 1.1,
            "board_strength": 1.0,
            "pool_inference": 0.75,
            "historical_cache": 0.55,
            "historical_cache_stale": 0.35,
            "unavailable": 0.0,
        }.get(market_context.hot_industry_source, 0.5)
        rank = market_context.industry_ranks.get(sector_name)
        if rank == 0:
            return round(2.8 * source_factor, 2)
        if rank == 1:
            return round(1.6 * source_factor, 2)
        if rank == 2:
            return round(0.9 * source_factor, 2)
        return round(-0.8 * source_factor, 2)

    @staticmethod
    def _market_state_text(market_context: PriorityMarketContext) -> str:
        parts = [f"市场状态：{market_context.market_state_label}。"]
        if market_context.market_bonus >= 2:
            parts.append("当前环境对低吸偏有利。")
        elif market_context.market_bonus <= -2:
            parts.append("当前环境对低吸偏谨慎。")
        else:
            parts.append("当前环境中性，先看结构和位置。")
        if not market_context.breadth_ready or not market_context.emotion_ready:
            waiting_parts: list[str] = []
            if not market_context.breadth_ready:
                waiting_parts.append("市场宽度")
            if not market_context.emotion_ready:
                waiting_parts.append("短线情绪")
            parts.append(f"{'、'.join(waiting_parts)}数据补齐中，当前先按偏谨慎处理。")
        elif market_context.transition_risk >= 0.35:
            parts.append("热点切换偏快，今天更适合等确认，不适合追价。")
        elif market_context.market_state_description:
            parts.append(market_context.market_state_description)
        if market_context.hot_industries:
            parts.append(f"当前热点：{' / '.join(market_context.hot_industries[:3])}。")
        return " ".join(parts)

    @staticmethod
    def _industry_rotation_text(
        candidate: LowBuyCandidateOut,
        market_context: PriorityMarketContext,
        bonus: float,
    ) -> str:
        sector_name = (candidate.sector_name or "").strip()
        if not sector_name:
            return "行业热度：未分类"
        rank = market_context.industry_ranks.get(sector_name)
        if rank == 0:
            return f"行业热度：{sector_name} 属于主线热点，加分 {bonus:+.1f}"
        if rank == 1:
            return f"行业热度：{sector_name} 属于次主线热点，加分 {bonus:+.1f}"
        if rank == 2:
            return f"行业热度：{sector_name} 属于热点延伸，加分 {bonus:+.1f}"
        if market_context.hot_industries:
            return f"行业热度：{sector_name} 不在当前重点热点内，修正 {bonus:+.1f}"
        return f"行业热度：当前暂无稳定热点，修正 {bonus:+.1f}"

    @staticmethod
    def _rank_hot_industries(hot_industries: list[str]) -> dict[str, int]:
        return {industry: index for index, industry in enumerate(hot_industries)}

    @staticmethod
    def _normalize_range(value: float, low: float, high: float) -> float:
        if high <= low:
            return 0.0
        clamped = min(max(value, low), high)
        return (clamped - low) / (high - low) * 100.0

    @staticmethod
    def _normalize_signed(value: float, midpoint: float, spread: float) -> float:
        if spread <= 0:
            return 0.0
        return max(-1.0, min(1.0, (value - midpoint) / spread))

    @staticmethod
    def _priority_action_summary(candidate: LowBuyCandidateOut) -> str:
        if candidate.false_breakout_flag:
            return "突破失败，先不接，等重新站回关键位。"
        if candidate.stall_after_volume_flag:
            return "放量滞涨，先看是否继续消化抛压。"
        if candidate.intraday_reversal_flag:
            return "冲高回落明显，先等承接重新转稳。"
        if candidate.buy_signal_state in {"buy_now", "soft_buy_now"}:
            trigger = candidate.trigger_condition or "价格到位并确认承接"
            return f"现在可处理，先试 {candidate.suggested_position_pct:.1f}% 仓位；{trigger}"
        if candidate.buy_signal_state == "near_entry":
            if candidate.entry_distance_pct <= 0:
                return "已到买点，等最后止跌/承接确认。"
            return f"距买点 {candidate.entry_distance_pct:.2f}%，先盯承接。"
        return "只跟踪，不追价，等价格到位。"

    @staticmethod
    def _priority_blocked_reason(candidate: LowBuyCandidateOut) -> str:
        if candidate.false_breakout_flag:
            return "刚突破就重新跌回关键位下方，疑似假突破。"
        if candidate.stall_after_volume_flag:
            return "成交放大但价格不再扩张，存在派发风险。"
        if candidate.intraday_reversal_flag:
            return "冲高回落后收在弱位，日内承接偏弱。"
        if candidate.buy_signal_state == "watch":
            if candidate.entry_distance_pct > 0:
                return f"未到买点，还差 {candidate.entry_distance_pct:.2f}%。"
            return candidate.trigger_condition or "结构还没完全确认。"
        if candidate.buy_signal_state == "near_entry":
            if candidate.entry_distance_pct <= 0:
                return "价格已到位，但仍缺止跌确认。"
            return f"价格未到位，还差 {candidate.entry_distance_pct:.2f}%。"
        return "当前优先级已足够，可直接处理。"
