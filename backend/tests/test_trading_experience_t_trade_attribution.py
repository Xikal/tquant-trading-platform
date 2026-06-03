from __future__ import annotations

from decimal import Decimal

from app.models.entities import PaperTrade
from app.services.trading_experience.t_trade_attribution import build_attribution
from backend.tests.trading_experience_fixtures import seed_key_level, seed_minutes, seed_paper, session_factory


def test_t_trade_attribution_marks_no_data_without_minute_coverage() -> None:
    Session = session_factory()
    db = Session()
    account = seed_paper(db)

    _, items = build_attribution(db, account_id=account.id, days=30)

    assert items[0].data_quality == "no_data"
    assert items[0].vs_no_t_trade_return_delta is None


def test_t_trade_attribution_uses_minute_coverage_when_available() -> None:
    Session = session_factory()
    db = Session()
    account = seed_paper(db)
    seed_minutes(db, days=20)
    seed_key_level(db, latest_price=9.0, support=9.8, resistance=11.0)

    _, items = build_attribution(db, account_id=account.id, days=30)

    assert items[0].data_quality == "ok"
    assert items[0].minute_data_coverage >= 0.6
    assert items[0].comparison_method == "paired_cashflow_vs_hold"
    assert items[0].vs_no_t_trade_return_delta is not None
    assert items[0].key_level_state == "support_broken"


def test_t_trade_attribution_filters_accounts_by_user() -> None:
    Session = session_factory()
    db = Session()
    other_account = seed_paper(db)

    resolved_account_id, items = build_attribution(db, account_id=other_account.id, user_id=2, days=30)

    assert resolved_account_id == other_account.id
    assert items == []


def test_t_trade_attribution_marks_insufficient_when_trade_fields_missing() -> None:
    Session = session_factory()
    db = Session()
    account = seed_paper(db)
    trade = db.query(PaperTrade).filter(PaperTrade.account_id == account.id).first()
    trade.price = Decimal("0")
    db.commit()
    seed_minutes(db, days=20)

    _, items = build_attribution(db, account_id=account.id, days=30)

    assert items[0].data_quality == "insufficient"
    assert any("price_missing" in item for item in items[0].completeness_issues)
    assert items[0].vs_no_t_trade_return_delta is None
