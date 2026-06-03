from __future__ import annotations

from app.services.trading_experience.holding_discipline import build_hints
from backend.tests.trading_experience_fixtures import seed_daily_bars, seed_key_level, seed_paper, session_factory


def test_holding_discipline_outputs_breakdown_without_order_blocking() -> None:
    Session = session_factory()
    db = Session()
    seed_daily_bars(db)
    account = seed_paper(db)
    seed_key_level(db, latest_price=9.0, support=9.8, resistance=11.0)

    resolved_account_id, hints = build_hints(db, account_id=account.id)

    assert resolved_account_id == account.id
    assert any(item.hint_code == "break_down" for item in hints)
    assert any(item.hint_code == "no_add_down_warning" for item in hints)
    assert any("AKeyLevel" in evidence for item in hints for evidence in item.evidence)
    assert all("production_score" not in item.model_dump() for item in hints)


def test_holding_discipline_filters_accounts_by_user() -> None:
    Session = session_factory()
    db = Session()
    seed_daily_bars(db)
    other_account = seed_paper(db)

    resolved_account_id, hints = build_hints(db, account_id=other_account.id, user_id=2)

    assert resolved_account_id == other_account.id
    assert hints == []


def test_holding_discipline_requires_key_level_cache() -> None:
    Session = session_factory()
    db = Session()
    seed_daily_bars(db)
    account = seed_paper(db)

    _, hints = build_hints(db, account_id=account.id)

    assert hints[0].hint_code == "watch_cadence"
    assert hints[0].data_quality == "insufficient"
    assert any("AKeyLevel 缓存缺失" in item for item in hints[0].evidence)
