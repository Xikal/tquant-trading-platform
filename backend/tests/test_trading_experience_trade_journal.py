from __future__ import annotations

import pytest

from app.services.trading_experience.schemas import TradeJournalEntryCreate
from app.services.trading_experience.trade_journal import create_entry, list_entries
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
