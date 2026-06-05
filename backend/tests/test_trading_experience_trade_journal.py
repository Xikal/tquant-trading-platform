from __future__ import annotations

import pytest

from app.services.trading_experience.schemas import TradeJournalEntryCreate, TradeJournalEntryUpdate
from app.services.trading_experience.trade_journal import create_entry, delete_entry, list_entries, update_entry
from backend.tests.trading_experience_fixtures import seed_paper, session_factory


def test_trade_journal_creates_manual_discipline_entry() -> None:
    Session = session_factory()
    db = Session()
    account = seed_paper(db)

    entry = create_entry(
        db,
        TradeJournalEntryCreate(
            account_id=account.id,
            symbol="600000",
            action="note",
            reason_text="记录盘后纪律复盘",
            discipline_flags={"stop_loss_set": True},
            mistake_tags=["late_plan"],
        ),
        user_id=1,
    )

    assert entry.entry_id > 0
    assert entry.discipline_flags["stop_loss_set"] is True
    rows = list_entries(db, user_id=1, account_id=account.id)
    assert rows[0].symbol == "600000"


def test_trade_journal_blocks_forbidden_copy() -> None:
    Session = session_factory()
    db = Session()

    with pytest.raises(ValueError):
        create_entry(
            db,
            TradeJournalEntryCreate(symbol="600000", action="note", reason_text="计划买入"),
            user_id=1,
        )


def test_trade_journal_rejects_other_users_account() -> None:
    Session = session_factory()
    db = Session()
    account = seed_paper(db)

    with pytest.raises(ValueError, match="paper_account_not_found"):
        create_entry(
            db,
            TradeJournalEntryCreate(account_id=account.id, symbol="600000", action="note"),
            user_id=2,
        )

    assert list_entries(db, user_id=2, account_id=account.id) == []


def test_trade_journal_can_update_and_delete_own_entry() -> None:
    Session = session_factory()
    db = Session()

    created = create_entry(
        db,
        TradeJournalEntryCreate(
            symbol="600000",
            action="note",
            reason_text="初始复盘",
            discipline_flags={},
            mistake_tags=[],
        ),
        user_id=1,
    )

    updated = update_entry(
        db,
        created.entry_id,
        TradeJournalEntryUpdate(reason_text="修正后的复盘", mistake_tags=["discipline_miss"]),
        user_id=1,
    )

    assert updated.reason_text == "修正后的复盘"
    assert updated.mistake_tags == ["discipline_miss"]

    delete_entry(db, created.entry_id, user_id=1)

    assert list_entries(db, user_id=1, symbol="600000") == []


def test_trade_journal_update_delete_respects_user_scope() -> None:
    Session = session_factory()
    db = Session()
    created = create_entry(
        db,
        TradeJournalEntryCreate(symbol="600000", action="note", reason_text="用户一复盘"),
        user_id=1,
    )

    with pytest.raises(ValueError, match="trade_journal_entry_not_found"):
        update_entry(db, created.entry_id, TradeJournalEntryUpdate(reason_text="越权修正"), user_id=2)

    with pytest.raises(ValueError, match="trade_journal_entry_not_found"):
        delete_entry(db, created.entry_id, user_id=2)
