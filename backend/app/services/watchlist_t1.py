from __future__ import annotations

from datetime import date, datetime
from typing import Union

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import UserWatchlist, Watchlist
from app.services.market.trading_calendar import last_a_share_trading_day, next_a_share_trading_day

WatchlistRow = Union[Watchlist, UserWatchlist]


def mark_watchlist_t1_availability(row: WatchlistRow, *, today: date) -> None:
    """Mark newly locked A-share holdings as available on the next trading day."""

    if int(row.base_position or 0) > 0 and int(row.available_position or 0) < int(row.base_position or 0):
        row.available_position_date = next_a_share_trading_day(today)
        return
    row.available_position_date = None


def refresh_watchlist_t1_availability(
    db: Session,
    *,
    model: type[Watchlist] | type[UserWatchlist],
    user_id: int | None = None,
    today: date,
) -> bool:
    """Unlock T+1 holdings whose available date has reached the latest trading day."""

    available_as_of = last_a_share_trading_day(today)
    filters = [model.base_position > 0, model.available_position < model.base_position]
    if user_id is not None and model is UserWatchlist:
        filters.append(UserWatchlist.user_id == user_id)

    rows = db.execute(select(model).where(*filters)).scalars().all()
    changed = False
    for row in rows:
        available_date = row.available_position_date or _legacy_available_date(row.created_at)
        if available_date is None:
            continue
        if row.available_position_date != available_date:
            row.available_position_date = available_date
            changed = True
        if available_date <= available_as_of:
            row.available_position = row.base_position
            row.available_position_date = None
            changed = True

    if changed:
        db.commit()
    return changed


def _legacy_available_date(created_at: datetime | None) -> date | None:
    if created_at is None:
        return None
    return next_a_share_trading_day(created_at.date())
