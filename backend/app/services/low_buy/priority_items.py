from __future__ import annotations

from typing import Protocol

from app.models.schemas import LowBuyCandidateOut, LowBuyPriorityBoardItemOut
from app.services.low_buy.priority_family import (
    priority_recommendation_duration_text,
    recommendation_days_by_title,
    strategy_performance_text,
)
from app.services.low_buy.priority_types import PriorityMarketContext, StrategyHit, PriorityCandidate
from app.services.low_buy.strategy_families import resolve_strategy_family_label


class PriorityItemBuilder(Protocol):
    def _aggregate_strategy_weight(self, hits: list[StrategyHit]) -> float: ...

    def _effective_strategy_count(self, hits: list[StrategyHit]) -> int: ...

    def _effective_family_count(self, hits: list[StrategyHit]) -> int: ...

    def _final_rank_score(
        self,
        candidate: LowBuyCandidateOut,
        aggregate_weight: float,
        family_count: int,
        strategy_weight: float,
        market_context: PriorityMarketContext,
    ) -> float: ...

    def _sector_rotation_bonus(self, candidate: LowBuyCandidateOut, market_context: PriorityMarketContext) -> float: ...

    def _industry_rotation_text(
        self,
        candidate: LowBuyCandidateOut,
        market_context: PriorityMarketContext,
        bonus: float,
    ) -> str: ...

    def _priority_action_summary(self, candidate: LowBuyCandidateOut) -> str: ...

    def _priority_blocked_reason(self, candidate: LowBuyCandidateOut) -> str: ...

    def _display_strategy_titles(self, hits: list[StrategyHit]) -> list[str]: ...


def build_priority_items(
    *,
    rows: list[PriorityCandidate],
    market_context: PriorityMarketContext,
    builder: PriorityItemBuilder,
) -> list[LowBuyPriorityBoardItemOut]:
    items: list[LowBuyPriorityBoardItemOut] = []
    for row in rows:
        if not row.hits:
            continue
        item = _build_priority_item(
            row=row,
            market_context=market_context,
            builder=builder,
        )
        items.append(item)
    return items


def _build_priority_item(
    *,
    row: PriorityCandidate,
    market_context: PriorityMarketContext,
    builder: PriorityItemBuilder,
) -> LowBuyPriorityBoardItemOut:
    aggregate_weight = builder._aggregate_strategy_weight(row.hits)
    strategy_count = builder._effective_strategy_count(row.hits)
    family_count = builder._effective_family_count(row.hits)
    primary_hit = max(
        row.hits,
        key=lambda hit: builder._final_rank_score(
            candidate=hit.candidate,
            aggregate_weight=aggregate_weight,
            family_count=family_count,
            strategy_weight=hit.strategy_weight_score + hit.context_bonus,
            market_context=market_context,
        ),
    )
    candidate = primary_hit.candidate
    strategy_titles = builder._display_strategy_titles(row.hits)
    recommendation_days_by_title_map = recommendation_days_by_title(row.hits)
    recommendation_days = max(recommendation_days_by_title_map.values(), default=candidate.recommendation_days)
    industry_rotation_bonus = builder._sector_rotation_bonus(candidate, market_context)
    kelly_half_position_pct = round(float(getattr(primary_hit.performance, "kelly_half_position_pct", 0.0) or 0.0), 2)
    return LowBuyPriorityBoardItemOut(
        symbol=candidate.symbol,
        name=candidate.name,
        sector_name=candidate.sector_name,
        strategy_key=primary_hit.strategy_key,
        strategy_title=primary_hit.strategy_title,
        strategy_titles=strategy_titles,
        strategy_count=strategy_count,
        family_count=family_count,
        strategy_family=primary_hit.family_key,
        strategy_family_text=resolve_strategy_family_label(primary_hit.strategy_key),
        latest_price=candidate.latest_price,
        change_pct=candidate.change_pct,
        quote_timestamp=candidate.quote_timestamp,
        data_quality=candidate.data_quality,
        data_quality_text=candidate.data_quality_text,
        data_quality_tags=candidate.data_quality_tags,
        market_state_category=candidate.market_state_category,
        market_state_category_text=candidate.market_state_category_text,
        buy_signal_state=candidate.buy_signal_state,
        buy_signal_text=candidate.buy_signal_text,
        priority_score=builder._final_rank_score(
            candidate=candidate,
            aggregate_weight=aggregate_weight,
            family_count=family_count,
            strategy_weight=primary_hit.strategy_weight_score + primary_hit.context_bonus,
            market_context=market_context,
        ),
        strategy_weight_score=round(aggregate_weight, 2),
        industry_rotation_bonus=industry_rotation_bonus,
        industry_rotation_text=builder._industry_rotation_text(candidate, market_context, industry_rotation_bonus),
        industry_tier=candidate.industry_tier,
        industry_tier_text=candidate.industry_tier_text,
        industry_position_multiplier=candidate.industry_position_multiplier,
        position_breakdown_text=candidate.position_breakdown_text,
        action_summary=builder._priority_action_summary(candidate),
        blocked_reason=builder._priority_blocked_reason(candidate),
        trigger_condition=candidate.trigger_condition,
        invalid_condition=candidate.invalid_condition,
        risk_tier=candidate.risk_tier,
        next_watch_price=candidate.next_watch_price,
        leader_rank=candidate.leader_rank,
        mainline_rank=candidate.mainline_rank,
        mainline_tier=candidate.mainline_tier,
        mainline_tier_text=candidate.mainline_tier_text,
        execution_quality_score=candidate.execution_quality_score,
        execution_quality_text=candidate.execution_quality_text,
        strategy_performance_text=strategy_performance_text(primary_hit.performance),
        kelly_half_position_pct=kelly_half_position_pct,
        kelly_position_text=_kelly_position_text(kelly_half_position_pct),
        atr_pct=candidate.atr_pct,
        atr_window=candidate.atr_window,
        atr_source=candidate.atr_source,
        volatility_position_pct=candidate.volatility_position_pct,
        final_position_cap_pct=candidate.final_position_cap_pct,
        position_cap_reason=candidate.position_cap_reason,
        next_day_event_plan=candidate.next_day_event_plan,
        entry_zone_low=candidate.entry_zone_low,
        entry_zone_high=candidate.entry_zone_high,
        stop_loss=candidate.stop_loss,
        suggested_position_pct=candidate.suggested_position_pct,
        suggested_position_text=candidate.suggested_position_text,
        recommendation_start_date=candidate.recommendation_start_date,
        recommendation_days=recommendation_days,
        strategy_recommendation_days=recommendation_days_by_title_map,
        recommendation_duration_text=priority_recommendation_duration_text(
            candidate=candidate,
            recommendation_days_by_title=recommendation_days_by_title_map,
        ),
    )


def _kelly_position_text(kelly_half_position_pct: float) -> str:
    if kelly_half_position_pct <= 0:
        return ""
    return f"半凯利建议仓位上限 {kelly_half_position_pct:.1f}%"
