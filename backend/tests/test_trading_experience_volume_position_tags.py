from __future__ import annotations

from datetime import date

import pytest

from app.models.entities import DailyBarSnapshot
from app.services.trading_experience.volume_position_tags import build_tags
from backend.tests.trading_experience_fixtures import seed_daily_bars, seed_key_level, session_factory


def test_volume_position_tags_trigger_high_volume_distribution() -> None:
    Session = session_factory()
    db = Session()
    seed_daily_bars(db, pct=9.2)
    row = db.query(DailyBarSnapshot).filter(DailyBarSnapshot.trade_date == date(2026, 5, 24)).one()
    row.volume = 6_000_000
    row.close_price = 10.05
    row.high_price = 11.00
    row.low_price = 10.00
    db.commit()
    seed_key_level(db, latest_price=10.05, support=9.8, resistance=10.2)

    tags = build_tags(db, "600000", trade_date=date(2026, 5, 24))

    assert any(item.tag_code == "high_vol_distribution_risk" for item in tags)
    assert any("AKeyLevel" in evidence for item in tags for evidence in item.evidence)
    assert all("production_score" not in item.model_dump() for item in tags)


@pytest.mark.parametrize(
    ("tag_code", "row_updates", "key_level_kwargs"),
    [
        (
            "low_vol_grind_down_risk",
            {"volume": 500_000, "pct_chg": -2.0, "close_price": 9.4, "high_price": 9.8, "low_price": 9.3},
            {"latest_price": 9.4, "support": 9.8, "resistance": 10.8},
        ),
        (
            "healthy_pullback_observe",
            {"volume": 1_100_000, "pct_chg": -1.0, "close_price": 9.85, "high_price": 10.0, "low_price": 9.7},
            {"latest_price": 9.85, "support": 9.8, "resistance": 11.0},
        ),
        (
            "up_shrink_down_expand_risk",
            {"volume": 2_600_000, "pct_chg": -1.5, "close_price": 10.6, "high_price": 10.9, "low_price": 10.4},
            {"latest_price": 10.6, "support": 9.8, "resistance": 10.9},
        ),
        (
            "blowoff_overheat_risk",
            {"volume": 5_000_000, "pct_chg": 8.5, "close_price": 10.25, "high_price": 10.28, "low_price": 9.8},
            {"latest_price": 10.25, "support": 9.8, "resistance": 10.3},
        ),
        (
            "price_volume_divergence_risk",
            {"volume": 2_000_000, "pct_chg": 1.5, "close_price": 10.4, "high_price": 11.0, "low_price": 10.2},
            {"latest_price": 10.4, "support": 9.8, "resistance": 10.9},
        ),
    ],
)
def test_volume_position_tags_trigger_each_supported_tag(tag_code, row_updates, key_level_kwargs) -> None:  # noqa: ANN001
    Session = session_factory()
    db = Session()
    seed_daily_bars(db, pct=9.2)
    previous = db.query(DailyBarSnapshot).filter(DailyBarSnapshot.trade_date == date(2026, 5, 23)).one()
    previous.pct_chg = 2.0
    row = db.query(DailyBarSnapshot).filter(DailyBarSnapshot.trade_date == date(2026, 5, 24)).one()
    for field, value in row_updates.items():
        setattr(row, field, value)
    db.commit()
    seed_key_level(db, **key_level_kwargs)

    tags = build_tags(db, "600000", trade_date=date(2026, 5, 24))

    assert any(item.tag_code == tag_code for item in tags), [item.tag_code for item in tags]


@pytest.mark.parametrize(
    "tag_code",
    [
        "high_vol_distribution_risk",
        "low_vol_grind_down_risk",
        "healthy_pullback_observe",
        "up_shrink_down_expand_risk",
        "blowoff_overheat_risk",
        "price_volume_divergence_risk",
    ],
)
def test_volume_position_tags_do_not_trigger_without_matching_shape(tag_code: str) -> None:
    Session = session_factory()
    db = Session()
    seed_daily_bars(db, pct=0.2)
    row = db.query(DailyBarSnapshot).filter(DailyBarSnapshot.trade_date == date(2026, 5, 24)).one()
    row.volume = 1_200_000
    row.pct_chg = 0.2
    row.close_price = 10.0
    row.high_price = 10.2
    row.low_price = 9.8
    db.commit()
    seed_key_level(db, latest_price=10.0, support=9.7, resistance=11.0)

    tags = build_tags(db, "600000", trade_date=date(2026, 5, 24))

    assert all(item.tag_code != tag_code for item in tags)


def test_volume_position_tags_mark_insufficient_when_key_level_missing() -> None:
    Session = session_factory()
    db = Session()
    seed_daily_bars(db, pct=9.2)

    tags = build_tags(db, "600000", trade_date=date(2026, 5, 24))

    assert tags[0].tag_code == "insufficient_key_level"
    assert tags[0].data_quality == "insufficient"


def test_volume_position_tags_mark_insufficient_history() -> None:
    Session = session_factory()
    db = Session()

    tags = build_tags(db, "600000", trade_date=date(2026, 5, 24))

    assert tags[0].data_quality == "insufficient"
