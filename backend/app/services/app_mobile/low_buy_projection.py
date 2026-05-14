from __future__ import annotations

from app.models.schemas import (
    AppLowBuyPriorityBoard,
    LowBuyCandidateOut,
    LowBuyPriorityFamilyPerformanceOut,
    LowBuyPriorityFamilySectionOut,
    LowBuyPriorityBoardItemOut,
    LowBuyScreenerResponse,
    LowBuyStrategyPerformanceOut,
)
from app.services.low_buy.strategy_families import resolve_strategy_family, resolve_strategy_family_label
from app.services.low_buy.simple_decision import build_daily_decision, build_simple_buckets, enrich_priority_items

_SIGNAL_PRIORITY = {
    "buy_now": 4,
    "soft_buy_now": 3,
    "near_entry": 2,
    "watch": 1,
    "avoid": 0,
}


def build_priority_board(payload: LowBuyScreenerResponse, limit: int = 12) -> AppLowBuyPriorityBoard:
    unique_candidates = _dedupe_candidates(payload.confirmed_candidates + payload.candidates)
    items = [_to_priority_item(candidate) for candidate in unique_candidates]
    items.sort(key=_priority_sort_key, reverse=True)
    limited_items = enrich_priority_items(items[:limit])
    board = AppLowBuyPriorityBoard(
        as_of_date=payload.as_of_date,
        latest_trade_date=payload.latest_trade_date,
        updated_at=payload.full_scan_updated_at or payload.as_of_date,
        total_candidates=len(items),
        immediate_count=sum(item.buy_signal_state in {"buy_now", "soft_buy_now"} for item in items),
        focus_count=sum(item.buy_signal_state == "near_entry" for item in items),
        track_count=sum(item.buy_signal_state == "watch" for item in items),
        market_state=payload.market_state,
        market_state_text=payload.market_state_text,
        market_bonus=payload.market_bonus,
        market_state_strength=payload.market_state_strength,
        regime_confidence=payload.regime_confidence,
        state_persistence_days=payload.state_persistence_days,
        transition_risk=payload.transition_risk,
        breadth_ready=payload.breadth_ready,
        emotion_ready=payload.emotion_ready,
        stock_up_ratio=payload.stock_up_ratio,
        stock_median_change=payload.stock_median_change,
        style_divergence=payload.style_divergence,
        hot_turnover=payload.hot_turnover,
        hot_overlap_ratio=payload.hot_overlap_ratio,
        limit_down_count=payload.limit_down_count,
        limit_up_count=payload.limit_up_count,
        board_height=payload.board_height,
        previous_board_height=payload.previous_board_height,
        promotion_ratio=payload.promotion_ratio,
        broken_board_ratio=payload.broken_board_ratio,
        promotion_break_gap=payload.promotion_break_gap,
        promotion_break_pressure=payload.promotion_break_pressure,
        high_flyer_retreat_ratio=payload.high_flyer_retreat_ratio,
        high_flyer_gap_speed=payload.high_flyer_gap_speed,
        distribution_pressure=payload.distribution_pressure,
        emotion_temperature=payload.emotion_temperature,
        emotion_temperature_text=payload.emotion_temperature_text,
        emotion_temperature_score=payload.emotion_temperature_score,
        hot_industries=payload.hot_industries,
        hot_industry_source=payload.hot_industry_source,
        hot_industry_source_text=payload.hot_industry_source_text,
        mainline_lifecycle_state=payload.mainline_lifecycle_state,
        mainline_lifecycle_text=payload.mainline_lifecycle_text,
        portfolio_risk=payload.portfolio_risk,
        family_sections=_build_family_sections(items=items, performance=payload.performance, limit=limit),
        items=limited_items,
    )
    board.daily_decision = build_daily_decision(board)
    board.simple_buckets = build_simple_buckets(limited_items)
    return board


def _dedupe_candidates(candidates: list[LowBuyCandidateOut]) -> list[LowBuyCandidateOut]:
    seen: set[str] = set()
    result: list[LowBuyCandidateOut] = []
    for candidate in candidates:
        if candidate.symbol in seen:
            continue
        seen.add(candidate.symbol)
        result.append(candidate)
    return result


def _to_priority_item(candidate: LowBuyCandidateOut) -> LowBuyPriorityBoardItemOut:
    return LowBuyPriorityBoardItemOut(
        symbol=candidate.symbol,
        name=candidate.name,
        strategy_key=candidate.strategy_key,
        strategy_title=candidate.strategy_title,
        strategy_titles=[candidate.strategy_title],
        strategy_count=1,
        family_count=1,
        strategy_family=resolve_strategy_family(candidate.strategy_key),
        strategy_family_text=resolve_strategy_family_label(candidate.strategy_key),
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
        priority_score=candidate.score,
        strategy_weight_score=candidate.score,
        industry_rotation_bonus=0.0,
        industry_rotation_text=candidate.sector_name or "",
        industry_tier=candidate.industry_tier,
        industry_tier_text=candidate.industry_tier_text,
        industry_position_multiplier=candidate.industry_position_multiplier,
        position_breakdown_text=candidate.position_breakdown_text,
        action_summary=candidate.buy_signal_hint or candidate.execution_note or candidate.summary_reason,
        blocked_reason=(candidate.risks[0] if candidate.buy_signal_state == "avoid" and candidate.risks else ""),
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
        atr_pct=candidate.atr_pct,
        atr_window=candidate.atr_window,
        atr_source=candidate.atr_source,
        volatility_position_pct=candidate.volatility_position_pct,
        final_position_cap_pct=candidate.final_position_cap_pct,
        position_cap_reason=candidate.position_cap_reason,
        entry_zone_low=candidate.entry_zone_low,
        entry_zone_high=candidate.entry_zone_high,
        stop_loss=candidate.stop_loss,
        suggested_position_pct=candidate.suggested_position_pct,
        suggested_position_text=candidate.suggested_position_text,
        recommendation_start_date=candidate.recommendation_start_date,
        recommendation_days=candidate.recommendation_days,
        strategy_recommendation_days=candidate.strategy_recommendation_days,
        recommendation_duration_text=candidate.recommendation_duration_text,
    )


def _build_family_sections(
    *,
    items: list[LowBuyPriorityBoardItemOut],
    performance: LowBuyStrategyPerformanceOut | None,
    limit: int,
) -> list[LowBuyPriorityFamilySectionOut]:
    grouped: dict[str, list[LowBuyPriorityBoardItemOut]] = {}
    for item in items:
        grouped.setdefault(item.strategy_family or "uncategorized", []).append(item)
    sections: list[LowBuyPriorityFamilySectionOut] = []
    for family_key, family_items in grouped.items():
        ordered_items = sorted(family_items, key=_priority_sort_key, reverse=True)
        family_text = ordered_items[0].strategy_family_text or resolve_strategy_family_label(family_key)
        sections.append(
            LowBuyPriorityFamilySectionOut(
                family_key=family_key,
                family_text=family_text,
                total_candidates=len(ordered_items),
                immediate_count=sum(item.buy_signal_state in {"buy_now", "soft_buy_now"} for item in ordered_items),
                focus_count=sum(item.buy_signal_state == "near_entry" for item in ordered_items),
                track_count=sum(item.buy_signal_state == "watch" for item in ordered_items),
                avg_priority_score=round(sum(item.priority_score for item in ordered_items) / max(len(ordered_items), 1), 2),
                top_strategy_titles=_unique_strategy_titles(ordered_items),
                performance=_family_performance(
                    family_key=family_key,
                    family_text=family_text,
                    performance=performance,
                ),
                items=ordered_items[:limit],
            )
        )
    sections.sort(key=lambda section: (section.immediate_count, section.focus_count, section.avg_priority_score), reverse=True)
    return sections


def _family_performance(
    *,
    family_key: str,
    family_text: str,
    performance: LowBuyStrategyPerformanceOut | None,
) -> LowBuyPriorityFamilyPerformanceOut | None:
    if performance is None:
        return None
    return LowBuyPriorityFamilyPerformanceOut(
        family_key=family_key,
        family_text=family_text,
        strategy_count=1,
        evaluated_signals=performance.evaluated_signals,
        filled_signals=performance.filled_signals,
        not_filled_signals=performance.not_filled_signals,
        hit_count=performance.hit_count,
        net_win_rate=performance.net_win_rate,
        avg_net_return_pct=performance.avg_net_return_pct,
        not_filled_rate=performance.not_filled_rate,
        stop_loss_rate=performance.stop_loss_rate,
        hit_rate=performance.hit_rate,
    )


def _unique_strategy_titles(items: list[LowBuyPriorityBoardItemOut]) -> list[str]:
    titles: list[str] = []
    for item in items:
        for title in item.strategy_titles or [item.strategy_title]:
            if title not in titles:
                titles.append(title)
    return titles[:4]


def _priority_sort_key(item: LowBuyPriorityBoardItemOut) -> tuple[int, float]:
    return (_SIGNAL_PRIORITY.get(item.buy_signal_state, 0), item.priority_score)
