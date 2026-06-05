from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session

from app.models.entities import (
    DailyBarSnapshot,
    Instrument,
    MinuteBarSnapshot,
    PaperAccount,
    PaperPosition,
    PaperTrade,
    TradingExperienceReviewPoolItem,
    TradingExperienceSnapshot,
    TradingExperienceTradeJournalEntry,
)


def latest_trade_date(db: Session) -> date | None:
    return db.execute(select(func.max(DailyBarSnapshot.trade_date))).scalar_one_or_none()


def daily_rows_for_date(db: Session, trade_date: date, *, limit: int = 500, board_filter: str = "include_all") -> list[Any]:
    statement = (
        select(DailyBarSnapshot, Instrument.name, Instrument.sector_name)
        .outerjoin(Instrument, Instrument.symbol == DailyBarSnapshot.symbol)
        .where(DailyBarSnapshot.trade_date == trade_date, DailyBarSnapshot.instrument_type == "stock")
    )
    if board_filter == "main_only":
        statement = statement.where(or_(DailyBarSnapshot.symbol.like("60%"), DailyBarSnapshot.symbol.like("00%")))
    return list(
        db.execute(
            statement.order_by(DailyBarSnapshot.pct_chg.desc(), DailyBarSnapshot.amount.desc()).limit(limit)
        ).all()
    )


def symbol_history(db: Session, symbol: str, *, end_date: date | None = None, days: int = 20) -> list[DailyBarSnapshot]:
    statement = select(DailyBarSnapshot).where(DailyBarSnapshot.symbol == symbol)
    if end_date:
        statement = statement.where(DailyBarSnapshot.trade_date <= end_date)
    return list(db.execute(statement.order_by(DailyBarSnapshot.trade_date.desc()).limit(days)).scalars())[::-1]


def next_symbol_rows(db: Session, symbol: str, pool_date: date, *, days: int = 3) -> list[DailyBarSnapshot]:
    return list(
        db.execute(
            select(DailyBarSnapshot)
            .where(DailyBarSnapshot.symbol == symbol, DailyBarSnapshot.trade_date > pool_date)
            .order_by(DailyBarSnapshot.trade_date.asc())
            .limit(days)
        ).scalars()
    )


def daily_rows_between(db: Session, *, start_date: date, end_date: date) -> list[DailyBarSnapshot]:
    return list(
        db.execute(
            select(DailyBarSnapshot)
            .where(
                DailyBarSnapshot.trade_date >= start_date,
                DailyBarSnapshot.trade_date <= end_date,
                DailyBarSnapshot.instrument_type == "stock",
            )
            .order_by(DailyBarSnapshot.symbol.asc(), DailyBarSnapshot.trade_date.asc())
        ).scalars()
    )


def upsert_review_pool_item(db: Session, row: TradingExperienceReviewPoolItem) -> TradingExperienceReviewPoolItem:
    existing = db.execute(
        select(TradingExperienceReviewPoolItem).where(
            TradingExperienceReviewPoolItem.pool_date == row.pool_date,
            TradingExperienceReviewPoolItem.symbol == row.symbol,
        )
    ).scalar_one_or_none()
    if not existing:
        db.add(row)
        return row
    for field in (
        "name",
        "status",
        "entry_pct",
        "volume_ratio",
        "mainline_state",
        "sector_role",
        "drop_reason",
        "tracked_days",
        "evidence_json",
        "data_quality",
        "as_of",
        "engine_version",
        "payload_json",
    ):
        setattr(existing, field, getattr(row, field))
    return existing


def stored_review_pool(db: Session, pool_date: date, *, limit: int) -> list[TradingExperienceReviewPoolItem]:
    return list(
        db.execute(
            select(TradingExperienceReviewPoolItem)
            .where(TradingExperienceReviewPoolItem.pool_date == pool_date)
            .order_by(TradingExperienceReviewPoolItem.entry_pct.desc(), TradingExperienceReviewPoolItem.id.asc())
            .limit(limit)
        ).scalars()
    )


def upsert_snapshot(
    db: Session,
    *,
    snapshot_type: str,
    snapshot_key: str,
    trade_date: date,
    data_quality: str,
    as_of: datetime,
    engine_version: str,
    payload: dict[str, Any],
) -> TradingExperienceSnapshot:
    row = db.execute(
        select(TradingExperienceSnapshot).where(
            TradingExperienceSnapshot.snapshot_type == snapshot_type,
            TradingExperienceSnapshot.snapshot_key == snapshot_key,
            TradingExperienceSnapshot.trade_date == trade_date,
            TradingExperienceSnapshot.engine_version == engine_version,
        )
    ).scalar_one_or_none()
    payload_json = json.dumps(payload, ensure_ascii=False, default=str, sort_keys=True)
    if row is None:
        row = TradingExperienceSnapshot(
            snapshot_type=snapshot_type,
            snapshot_key=snapshot_key,
            trade_date=trade_date,
            data_quality=data_quality,
            as_of=as_of,
            engine_version=engine_version,
            payload_json=payload_json,
        )
        db.add(row)
        return row
    row.data_quality = data_quality
    row.as_of = as_of
    row.payload_json = payload_json
    return row


def latest_snapshot(
    db: Session,
    *,
    snapshot_type: str,
    snapshot_key: str,
    trade_date: date | None = None,
    engine_version: str | None = None,
) -> TradingExperienceSnapshot | None:
    statement = select(TradingExperienceSnapshot).where(
        TradingExperienceSnapshot.snapshot_type == snapshot_type,
        TradingExperienceSnapshot.snapshot_key == snapshot_key,
    )
    if trade_date:
        statement = statement.where(TradingExperienceSnapshot.trade_date == trade_date)
    if engine_version:
        statement = statement.where(TradingExperienceSnapshot.engine_version == engine_version)
    return db.execute(
        statement.order_by(desc(TradingExperienceSnapshot.trade_date), desc(TradingExperienceSnapshot.id)).limit(1)
    ).scalar_one_or_none()


def snapshot_payload(row: TradingExperienceSnapshot | None) -> dict[str, Any]:
    if row is None:
        return {}
    return json_dict(row.payload_json)


def create_journal_entry(
    db: Session,
    *,
    user_id: int | None,
    account_id: int | None,
    symbol: str,
    action: str,
    reason_text: str,
    signal_source: str,
    discipline_flags: dict[str, bool],
    mistake_tags: list[str],
    engine_version: str,
) -> TradingExperienceTradeJournalEntry:
    row = TradingExperienceTradeJournalEntry(
        user_id=user_id,
        account_id=account_id,
        symbol=symbol,
        action=action,
        reason_text=reason_text,
        signal_source=signal_source,
        discipline_flags_json=json.dumps(discipline_flags, ensure_ascii=False, sort_keys=True),
        mistake_tags_json=json.dumps(mistake_tags, ensure_ascii=False),
        engine_version=engine_version,
        data_quality="ok",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def journal_entries(
    db: Session,
    *,
    user_id: int | None,
    account_id: int | None = None,
    symbol: str | None = None,
    limit: int = 50,
) -> list[TradingExperienceTradeJournalEntry]:
    statement = select(TradingExperienceTradeJournalEntry)
    if user_id is not None:
        statement = statement.where(TradingExperienceTradeJournalEntry.user_id == user_id)
    if account_id is not None:
        statement = statement.where(TradingExperienceTradeJournalEntry.account_id == account_id)
    if symbol:
        statement = statement.where(TradingExperienceTradeJournalEntry.symbol == symbol)
    return list(
        db.execute(statement.order_by(TradingExperienceTradeJournalEntry.created_at.desc()).limit(limit)).scalars()
    )


def journal_entry_by_id(
    db: Session,
    entry_id: int,
    *,
    user_id: int | None,
) -> TradingExperienceTradeJournalEntry | None:
    statement = select(TradingExperienceTradeJournalEntry).where(TradingExperienceTradeJournalEntry.id == entry_id)
    if user_id is not None:
        statement = statement.where(TradingExperienceTradeJournalEntry.user_id == user_id)
    return db.execute(statement).scalar_one_or_none()


def update_journal_entry(
    db: Session,
    row: TradingExperienceTradeJournalEntry,
    *,
    reason_text: str | None = None,
    discipline_flags: dict[str, bool] | None = None,
    mistake_tags: list[str] | None = None,
) -> TradingExperienceTradeJournalEntry:
    if reason_text is not None:
        row.reason_text = reason_text
    if discipline_flags is not None:
        row.discipline_flags_json = json.dumps(discipline_flags, ensure_ascii=False, sort_keys=True)
    if mistake_tags is not None:
        row.mistake_tags_json = json.dumps(mistake_tags, ensure_ascii=False)
    row.updated_at = datetime.now()
    db.commit()
    db.refresh(row)
    return row


def delete_journal_entry(db: Session, row: TradingExperienceTradeJournalEntry) -> None:
    db.delete(row)
    db.commit()


def active_paper_account(db: Session, account_id: int | None = None, *, user_id: int | None = None) -> PaperAccount | None:
    statement = select(PaperAccount).where(PaperAccount.status == "active")
    if user_id is not None:
        statement = statement.where(PaperAccount.user_id == user_id)
    if account_id is not None:
        statement = statement.where(PaperAccount.id == account_id)
    return db.execute(statement.order_by(PaperAccount.id.asc())).scalar_one_or_none()


def paper_account_for_user(db: Session, account_id: int, *, user_id: int | None) -> PaperAccount | None:
    statement = select(PaperAccount).where(PaperAccount.id == account_id)
    if user_id is not None:
        statement = statement.where(PaperAccount.user_id == user_id)
    return db.execute(statement).scalar_one_or_none()


def paper_positions(db: Session, account_id: int) -> list[PaperPosition]:
    return list(
        db.execute(
            select(PaperPosition)
            .where(PaperPosition.account_id == account_id, PaperPosition.quantity > 0)
            .order_by(PaperPosition.market_value.desc())
        ).scalars()
    )


def paper_trades(db: Session, account_id: int, *, days: int = 30) -> list[PaperTrade]:
    start = datetime.now() - timedelta(days=days)
    return list(
        db.execute(
            select(PaperTrade)
            .where(PaperTrade.account_id == account_id, PaperTrade.trade_time >= start)
            .order_by(PaperTrade.trade_time.asc(), PaperTrade.id.asc())
        ).scalars()
    )


def minute_coverage(db: Session, symbol: str, *, days: int = 30) -> float:
    start = date.today() - timedelta(days=days)
    trade_days = db.execute(
        select(func.count(func.distinct(MinuteBarSnapshot.trade_date))).where(
            MinuteBarSnapshot.symbol == symbol,
            MinuteBarSnapshot.trade_date >= start,
        )
    ).scalar_one()
    return min(1.0, float(trade_days or 0) / max(1, min(days, 20)))


def json_list(value: str) -> list[str]:
    try:
        parsed = json.loads(value or "[]")
    except json.JSONDecodeError:
        return []
    return [str(item) for item in parsed] if isinstance(parsed, list) else []


def json_dict_bool(value: str) -> dict[str, bool]:
    try:
        parsed = json.loads(value or "{}")
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {str(key): bool(item) for key, item in parsed.items()}


def json_dict(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value or "{}")
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}
