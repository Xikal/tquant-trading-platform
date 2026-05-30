from __future__ import annotations

from app.models.schema_defs.strategy_tracking import StrategyTrackingItemOut
from app.services.strategy_tracking_filters import filter_items


def test_strategy_tracking_filters_front_row_weighted_by_production_score() -> None:
    baseline = _item("000001", production_score=None, front_row_tier="unknown")
    weighted = _item("000002", production_score=88.0, front_row_tier="core_leader")

    result = filter_items(
        [baseline, weighted],
        lifecycle_status=None,
        data_quality=None,
        hit_entry=None,
        stopped=None,
        exclude_chinext=False,
        exclude_star=False,
        board_filter=None,
        user_status=None,
        strategy_variant="front_row_weighted",
    )

    assert [item.symbol for item in result] == ["000002"]
    assert result[0].display_lane == "front_row_weighted"
    assert result[0].paper_enabled is True


def test_strategy_tracking_filters_front_row_only_as_watch_only() -> None:
    item = _item("000002", production_score=88.0, front_row_tier="core_leader")

    result = filter_items(
        [item],
        lifecycle_status=None,
        data_quality=None,
        hit_entry=None,
        stopped=None,
        exclude_chinext=False,
        exclude_star=False,
        board_filter=None,
        user_status=None,
        strategy_variant="front_row_only",
    )

    assert len(result) == 1
    assert result[0].display_lane == "front_row_only"
    assert result[0].watch_only is True
    assert result[0].production_score is None


def _item(symbol: str, *, production_score: float | None, front_row_tier: str) -> StrategyTrackingItemOut:
    return StrategyTrackingItemOut(
        id=f"first_board:{symbol}:2026-04-20",
        symbol=symbol,
        name="测试",
        strategy_key="first_board",
        strategy_name="首板回调",
        signal_state="buy_now",
        production_score=production_score,
        watch_score=77.0,
        front_row_tier=front_row_tier,
    )
