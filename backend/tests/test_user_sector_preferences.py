from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.entities import User
from app.services.paper.admission import AdmissionFilter
from app.services.user_sector_preferences import (
    candidate_matches_excluded_sector,
    filter_priority_board_payload,
    filter_priority_board_response_for_user,
    UserSectorPreferenceService,
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


def test_priority_board_filter_cache_invalidates_on_user_preference_change() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, future=True)
    db = Session()
    db.add(User(id=7, username="tester", password_hash="x", is_active=True))
    db.commit()
    board = {
        "items": [
            {"symbol": "600000", "sector_name": "银行", "simple_bucket": "buy_now"},
            {"symbol": "002000", "sector_name": "半导体", "simple_bucket": "wait_price"},
        ],
        "family_sections": [],
        "simple_buckets": [
            {"key": "buy_now", "count": 1, "symbols": ["600000"]},
            {"key": "wait_price", "count": 1, "symbols": ["002000"]},
        ],
    }

    first = filter_priority_board_response_for_user(board, user_id=7, excluded_sectors={"银行"})
    UserSectorPreferenceService(db).replace_excluded_sectors(7, ["半导体"])
    second = filter_priority_board_response_for_user(board, user_id=7, excluded_sectors={"半导体"})

    assert [item["symbol"] for item in first["items"]] == ["002000"]
    assert [item["symbol"] for item in second["items"]] == ["600000"]
