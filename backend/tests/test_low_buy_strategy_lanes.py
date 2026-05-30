from __future__ import annotations

from app.services.low_buy.front_row_readiness import front_row_readiness_summary, plain_blocker_text
from app.services.low_buy.strategy_lanes import (
    FRONT_ROW_ONLY_VARIANT,
    FRONT_ROW_WEIGHTED_VARIANT,
    available_lane_payloads,
    lane_item_update,
    resolve_strategy_lane,
)


class _Item:
    production_score = 88.0
    watch_score = 76.0
    priority_score = 66.0
    front_row_tier = "core_leader"


def test_strategy_lane_metadata_keeps_roles_separate() -> None:
    lanes = {item["display_lane"]: item for item in available_lane_payloads()}

    assert lanes["baseline"]["title"] == "原低吸策略"
    assert lanes["baseline"]["production_enabled"] is True
    assert lanes[FRONT_ROW_WEIGHTED_VARIANT]["paper_enabled"] is True
    assert lanes[FRONT_ROW_WEIGHTED_VARIANT]["production_sort_replaced"] is False
    assert lanes[FRONT_ROW_ONLY_VARIANT]["watch_only"] is True


def test_front_row_only_lane_removes_production_score() -> None:
    update = lane_item_update(_Item(), FRONT_ROW_ONLY_VARIANT)

    assert update["production_score"] is None
    assert update["watch_only"] is True
    assert update["elite_watch_score"] == 76.0


def test_front_row_weighted_plain_status_is_shadow_paper() -> None:
    lane = resolve_strategy_lane(FRONT_ROW_WEIGHTED_VARIANT)

    assert lane.paper_enabled is True
    assert lane.production_enabled is False
    assert lane.production_sort_replaced is False


def test_readiness_missing_report_does_not_default_to_pass(monkeypatch) -> None:
    monkeypatch.setattr("app.services.low_buy.front_row_readiness._latest_report_path", lambda: None)

    summary = front_row_readiness_summary(FRONT_ROW_WEIGHTED_VARIANT)

    assert summary["status"] == "readiness_unknown"
    assert summary["recommend_small_traffic_observation"] is False
    assert "front_row_readiness_report_missing" in summary["blockers"]


def test_plain_blocker_text_is_user_friendly() -> None:
    assert plain_blocker_text("tick_data_insufficient_for_real_money_production") == "逐笔成交数据不足，暂不能用于真实交易判断"
