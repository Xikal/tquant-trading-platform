from __future__ import annotations

from app.services.low_buy.priority_items import build_priority_items
from app.services.low_buy.priority_types import PriorityCandidate
from app.services.low_buy.strategy_lanes import FRONT_ROW_ONLY_VARIANT, FRONT_ROW_WEIGHTED_VARIANT
from test_priority_weighting import _PriorityBoardService, _hit


def test_front_row_only_priority_item_is_watch_only_without_production_score() -> None:
    items = build_priority_items(
        rows=[PriorityCandidate(symbol="000001", hits=[_hit("first_board", 80.0)])],
        market_context=_market_context(),
        builder=_PriorityBoardService(),
        strategy_variant=FRONT_ROW_ONLY_VARIANT,
    )

    assert len(items) == 1
    assert items[0].display_lane == FRONT_ROW_ONLY_VARIANT
    assert items[0].watch_only is True
    assert items[0].production_score is None
    assert items[0].elite_watch_score is not None


def test_front_row_weighted_priority_item_is_paper_not_production_replacement() -> None:
    items = build_priority_items(
        rows=[PriorityCandidate(symbol="000001", hits=[_hit("first_board", 80.0)])],
        market_context=_market_context(),
        builder=_PriorityBoardService(),
        strategy_variant=FRONT_ROW_WEIGHTED_VARIANT,
    )

    assert items[0].display_lane == FRONT_ROW_WEIGHTED_VARIANT
    assert items[0].paper_enabled is True
    assert items[0].production_sort_replaced is False


def _market_context():
    from app.services.low_buy.priority_types import PriorityMarketContext

    return PriorityMarketContext(
        market_state="repair",
        market_bonus=0.0,
        market_state_strength=0.0,
        regime_confidence=0.0,
        state_persistence_days=1,
        transition_risk=0.0,
        market_state_label="repair",
        market_state_description="修复",
        breadth_ready=True,
        emotion_ready=True,
        stock_up_ratio=0.55,
        stock_median_change=0.0,
        style_divergence=0.0,
        hot_turnover=0.0,
        hot_overlap_ratio=0.0,
        limit_down_count=0,
        limit_up_count=0,
        board_height=0,
        previous_board_height=0,
        promotion_ratio=0.0,
        broken_board_ratio=0.0,
        promotion_break_gap=0.0,
        promotion_break_pressure=0.0,
        high_flyer_retreat_ratio=0.0,
        high_flyer_gap_speed=0.0,
        distribution_pressure=0.0,
        emotion_temperature="neutral",
        emotion_temperature_text="中性",
        emotion_temperature_score=0.0,
        hot_industries=[],
        hot_industry_source="",
        hot_industry_source_text="",
        mainline_lifecycle_state="",
        mainline_lifecycle_text="",
        industry_ranks={},
    )
