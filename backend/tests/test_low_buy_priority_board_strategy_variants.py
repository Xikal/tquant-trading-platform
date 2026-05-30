from __future__ import annotations

from os import environ

from app.core.config import get_settings
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


def test_priority_item_event_risk_gate_reduces_production_score() -> None:
    previous = environ.get("EVENT_RISK_PRODUCTION_BLOCK_ENABLED")
    environ["EVENT_RISK_PRODUCTION_BLOCK_ENABLED"] = "true"
    get_settings.cache_clear()
    market_context = _market_context(
        market_state_strength=0.82,
        limit_down_count=0,
        limit_up_count=42,
        stock_median_change=1.2,
        hot_industries=["银行", "证券", "保险"],
    )
    try:
        base_items = build_priority_items(
            rows=[PriorityCandidate(symbol="000001", hits=[_hit("first_board", 80.0)])],
            market_context=market_context,
            builder=_PriorityBoardService(),
            strategy_variant=FRONT_ROW_WEIGHTED_VARIANT,
        )
        risk_hit = _hit("first_board", 80.0)
        risk_hit.candidate = risk_hit.candidate.model_copy(
            update={
                "event_risk_gate": {
                    "decision": "reduce",
                    "score": 55.0,
                    "reasons": ["中风险事件触发降分并告警"],
                    "evidence": {"severity": "medium"},
                }
            }
        )

        risk_items = build_priority_items(
            rows=[PriorityCandidate(symbol="000001", hits=[risk_hit])],
            market_context=market_context,
            builder=_PriorityBoardService(),
            strategy_variant=FRONT_ROW_WEIGHTED_VARIANT,
        )
    finally:
        if previous is None:
            environ.pop("EVENT_RISK_PRODUCTION_BLOCK_ENABLED", None)
        else:
            environ["EVENT_RISK_PRODUCTION_BLOCK_ENABLED"] = previous
        get_settings.cache_clear()

    assert risk_items[0].production_score is not None
    assert base_items[0].production_score is not None
    assert risk_items[0].production_score < base_items[0].production_score
    assert risk_items[0].score_components["event_risk_gate"] < 0
    assert "event_risk_reduced" in risk_items[0].warning_tags


def _market_context(**overrides):
    from app.services.low_buy.priority_types import PriorityMarketContext

    values = {
        "market_state": "repair",
        "market_bonus": 0.0,
        "market_state_strength": 0.0,
        "regime_confidence": 0.0,
        "state_persistence_days": 1,
        "transition_risk": 0.0,
        "market_state_label": "repair",
        "market_state_description": "修复",
        "breadth_ready": True,
        "emotion_ready": True,
        "stock_up_ratio": 0.55,
        "stock_median_change": 0.0,
        "style_divergence": 0.0,
        "hot_turnover": 0.0,
        "hot_overlap_ratio": 0.0,
        "limit_down_count": 0,
        "limit_up_count": 0,
        "board_height": 0,
        "previous_board_height": 0,
        "promotion_ratio": 0.0,
        "broken_board_ratio": 0.0,
        "promotion_break_gap": 0.0,
        "promotion_break_pressure": 0.0,
        "high_flyer_retreat_ratio": 0.0,
        "high_flyer_gap_speed": 0.0,
        "distribution_pressure": 0.0,
        "emotion_temperature": "neutral",
        "emotion_temperature_text": "中性",
        "emotion_temperature_score": 0.0,
        "hot_industries": [],
        "hot_industry_source": "",
        "hot_industry_source_text": "",
        "mainline_lifecycle_state": "",
        "mainline_lifecycle_text": "",
        "industry_ranks": {},
    }
    values.update(overrides)
    return PriorityMarketContext(**values)
