from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.services.trading_experience import repository
from app.services.trading_experience.config import DISCIPLINE_FLAG_KEYS, ENGINE_VERSION
from app.services.trading_experience.guards import assert_no_forbidden_trading_copy
from app.services.trading_experience.schemas import TradeJournalEntryCreate, TradeJournalEntryOut


def create_entry(db: Session, payload: TradeJournalEntryCreate, *, user_id: int | None) -> TradeJournalEntryOut:
    assert_no_forbidden_trading_copy(payload.model_dump())
    account_id = payload.account_id
    if account_id is not None and repository.paper_account_for_user(db, account_id, user_id=user_id) is None:
        raise ValueError("paper_account_not_found")
    row = repository.create_journal_entry(
        db,
        user_id=user_id,
        account_id=account_id,
        symbol=payload.symbol,
        action=payload.action,
        reason_text=payload.reason_text,
        signal_source=payload.signal_source,
        discipline_flags=_normalize_flags(payload.discipline_flags),
        mistake_tags=payload.mistake_tags,
        engine_version=ENGINE_VERSION,
    )
    return _to_out(row)


def list_entries(
    db: Session,
    *,
    user_id: int | None,
    account_id: int | None = None,
    symbol: str | None = None,
    limit: int = 50,
) -> list[TradeJournalEntryOut]:
    if account_id is not None and repository.paper_account_for_user(db, account_id, user_id=user_id) is None:
        return []
    return [
        _to_out(row)
        for row in repository.journal_entries(db, user_id=user_id, account_id=account_id, symbol=symbol, limit=limit)
    ]


def _normalize_flags(flags: dict[str, bool]) -> dict[str, bool]:
    return {key: bool(flags.get(key, False)) for key in DISCIPLINE_FLAG_KEYS}


def _to_out(row) -> TradeJournalEntryOut:
    as_of = row.updated_at or row.created_at or datetime.now()
    return TradeJournalEntryOut(
        entry_id=row.id,
        user_id=row.user_id,
        account_id=row.account_id,
        symbol=row.symbol,
        action=row.action,
        reason_text=row.reason_text,
        signal_source=row.signal_source,
        discipline_flags=repository.json_dict_bool(row.discipline_flags_json),
        mistake_tags=repository.json_list(row.mistake_tags_json),
        data_quality=row.data_quality,
        as_of=as_of,
        engine_version=row.engine_version,
        source=row.source,
        research_only=True,
        created_at=row.created_at or as_of,
        updated_at=row.updated_at or as_of,
    )
