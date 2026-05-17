from __future__ import annotations

from app.models.schemas import (
    LowBuyPortfolioRiskOut,
    LowBuyPriorityBoardItemOut,
    LowBuyPriorityBoardResponse,
    LowBuyPriorityFamilySectionOut,
)
from app.services.low_buy.data_quality import build_market_data_quality, data_quality_payload
from app.services.low_buy.market_state_rules import compute_directional_bias, directional_bias_text
from app.services.low_buy.priority_types import PriorityBaseSnapshot
from app.services.low_buy.shared import datetime
from app.services.low_buy.simple_decision import build_daily_decision, build_simple_buckets, enrich_priority_items
from app.services.market.state_categories import standard_market_state_payload


def build_priority_board_response(
    *,
    base_snapshot: PriorityBaseSnapshot,
    items: list[LowBuyPriorityBoardItemOut],
    item_limit: int,
    family_sections: list[LowBuyPriorityFamilySectionOut],
    portfolio_risk: LowBuyPortfolioRiskOut,
    snapshot_warning: str,
    market_state_text: str,
) -> LowBuyPriorityBoardResponse:
    market_context = base_snapshot.market_context
    directional_bias = compute_directional_bias(
        market_context.market_state,
        regime_scores={"style_divergence": market_context.style_divergence},
        emotion_data={
            "broken_board_ratio": market_context.broken_board_ratio,
            "limit_down_count": market_context.limit_down_count or 0,
            "limit_up_count": market_context.limit_up_count,
        },
        mainline_strength={"strength": market_context.market_state_strength},
    )
    market_state_fields = standard_market_state_payload(market_context.market_state)
    quality_fields = data_quality_payload(
        build_market_data_quality(
            breadth_ready=market_context.breadth_ready,
            emotion_ready=market_context.emotion_ready,
            hot_industry_source=market_context.hot_industry_source,
            snapshot_warning=snapshot_warning,
        )
    )

    response = LowBuyPriorityBoardResponse(
        as_of_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        latest_trade_date=base_snapshot.latest_trade_date,
        latest_available_trade_date=base_snapshot.latest_available_trade_date,
        snapshot_warning=snapshot_warning,
        updated_at=base_snapshot.updated_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        total_candidates=len(items),
        immediate_count=sum(item.buy_signal_state in {"buy_now", "soft_buy_now"} for item in items),
        focus_count=sum(item.buy_signal_state in {"observe_confirmed", "near_entry"} for item in items),
        track_count=sum(item.buy_signal_state == "watch" for item in items),
        market_state=market_context.market_state,
        market_state_text=market_state_text,
        market_state_category=market_state_fields["market_state_category"],
        market_state_category_text=market_state_fields["market_state_category_text"],
        **quality_fields,
        directional_bias=directional_bias,
        directional_bias_text=directional_bias_text(directional_bias),
        market_bonus=market_context.market_bonus,
        market_state_strength=market_context.market_state_strength,
        regime_confidence=market_context.regime_confidence,
        state_persistence_days=market_context.state_persistence_days,
        transition_risk=market_context.transition_risk,
        breadth_ready=market_context.breadth_ready,
        emotion_ready=market_context.emotion_ready,
        stock_up_ratio=market_context.stock_up_ratio,
        stock_median_change=market_context.stock_median_change,
        style_divergence=market_context.style_divergence,
        hot_turnover=market_context.hot_turnover,
        hot_overlap_ratio=market_context.hot_overlap_ratio,
        limit_down_count=market_context.limit_down_count,
        limit_up_count=market_context.limit_up_count,
        board_height=market_context.board_height,
        previous_board_height=market_context.previous_board_height,
        promotion_ratio=market_context.promotion_ratio,
        broken_board_ratio=market_context.broken_board_ratio,
        promotion_break_gap=market_context.promotion_break_gap,
        promotion_break_pressure=market_context.promotion_break_pressure,
        high_flyer_retreat_ratio=market_context.high_flyer_retreat_ratio,
        high_flyer_gap_speed=market_context.high_flyer_gap_speed,
        distribution_pressure=market_context.distribution_pressure,
        emotion_temperature=market_context.emotion_temperature,
        emotion_temperature_text=market_context.emotion_temperature_text,
        emotion_temperature_score=market_context.emotion_temperature_score,
        hot_industries=market_context.hot_industries,
        hot_industry_source=market_context.hot_industry_source,
        hot_industry_source_text=market_context.hot_industry_source_text,
        mainline_lifecycle_state=market_context.mainline_lifecycle_state,
        mainline_lifecycle_text=market_context.mainline_lifecycle_text,
        portfolio_risk=portfolio_risk,
        missing_strategies=base_snapshot.missing_strategies,
        stale_strategies=base_snapshot.stale_strategies,
        family_sections=family_sections,
        items=items[:item_limit],
    )
    response.items = enrich_priority_items(response.items)
    response.daily_decision = build_daily_decision(response)
    response.simple_buckets = build_simple_buckets(response.items)
    return response
