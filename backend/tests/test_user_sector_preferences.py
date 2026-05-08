from __future__ import annotations

from app.services.paper.admission import AdmissionFilter
from app.services.user_sector_preferences import (
    candidate_matches_excluded_sector,
    filter_priority_board_payload,
)


def test_candidate_matches_excluded_sector_by_sector_name() -> None:
    assert candidate_matches_excluded_sector(
        {"symbol": "600000", "sector_name": "银行"},
        {"银行"},
    )
    assert not candidate_matches_excluded_sector(
        {"symbol": "600000", "sector_name": "半导体"},
        {"银行"},
    )


def test_filter_priority_board_payload_rebuilds_counts() -> None:
    payload = {
        "items": [
            {"symbol": "600000", "sector_name": "银行", "simple_bucket": "buy_now"},
            {"symbol": "002000", "sector_name": "半导体", "simple_bucket": "wait_price"},
        ],
        "family_sections": [
            {
                "family_key": "x",
                "family_text": "测试",
                "items": [
                    {"symbol": "600000", "sector_name": "银行", "simple_bucket": "buy_now", "priority_score": 90},
                    {"symbol": "002000", "sector_name": "半导体", "simple_bucket": "wait_price", "priority_score": 80},
                ],
            }
        ],
        "simple_buckets": [
            {"key": "buy_now", "count": 1, "symbols": ["600000"]},
            {"key": "wait_price", "count": 1, "symbols": ["002000"]},
        ],
    }

    filtered = filter_priority_board_payload(payload, {"银行"})

    assert filtered["total_candidates"] == 1
    assert filtered["immediate_count"] == 0
    assert filtered["focus_count"] == 1
    assert filtered["items"][0]["symbol"] == "002000"
    assert filtered["family_sections"][0]["total_candidates"] == 1
    assert filtered["simple_buckets"][0]["symbols"] == []
    assert filtered["simple_buckets"][1]["symbols"] == ["002000"]


def test_admission_filter_rejects_excluded_sector() -> None:
    report = AdmissionFilter(min_score=75).evaluate(
        signals=[
            {
                "symbol": "600000",
                "name": "浦发银行",
                "sector_name": "银行",
                "priority_score": 95,
                "buy_signal_state": "buy_now",
                "risk_tier": "note",
            }
        ],
        existing_positions=[],
        today_orders=[],
        market_direction="positive_t",
        excluded_sectors={"银行"},
    )

    assert not report.passed
    assert report.filtered[0].reason == "用户已排除银行，不自动买入"
