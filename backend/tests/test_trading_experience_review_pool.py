from __future__ import annotations

from datetime import date

from app.services.trading_experience.review_pool import build_review_pool
from backend.tests.trading_experience_fixtures import seed_daily_bars, session_factory


def test_review_pool_builds_strong_pool_and_retention_without_production_score() -> None:
    Session = session_factory()
    db = Session()
    seed_daily_bars(db, pct=9.2)

    items = build_review_pool(db, pool_date=date(2026, 5, 24), limit=10)

    assert len(items) == 1
    item = items[0]
    assert item.status == "dropped"
    assert item.drop_reason
    assert item.tracked_days == 3
    assert item.data_quality == "ok"
    assert "production_score" not in item.model_dump()


def test_review_pool_main_board_filter_is_applied_before_limit() -> None:
    Session = session_factory()
    db = Session()
    seed_daily_bars(db, symbol="300001", pct=20.0, sector="创业板样本")
    seed_daily_bars(db, symbol="688001", pct=19.0, sector="科创板样本")
    seed_daily_bars(db, symbol="600001", pct=10.0, sector="主板样本")

    items = build_review_pool(db, pool_date=date(2026, 5, 24), limit=2, board_filter="main_only")

    assert [item.symbol for item in items] == ["600001"]
    assert items[0].board_type == "main"
    assert items[0].board_name == "主板"


def test_review_pool_returns_empty_when_no_data() -> None:
    Session = session_factory()
    db = Session()

    assert build_review_pool(db, pool_date=date(2026, 5, 24), limit=10) == []
