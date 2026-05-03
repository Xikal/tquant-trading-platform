from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.timezone import beijing_now_string
from app.models.entities import User, UserWatchlist
from app.models.schema_defs.monitor import MonitorSnapshotResponse
from app.services.low_buy_screener import LowBuyScreenerService
from app.services.watchlist_signal_service import WatchlistSignalService

router = APIRouter(prefix="/monitor", dependencies=[Depends(get_current_user)])

watchlist_signal_service = WatchlistSignalService()
low_buy_screener = LowBuyScreenerService()


@router.get("/snapshot", response_model=MonitorSnapshotResponse)
def monitor_snapshot(
    priority_limit: int = Query(default=24, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MonitorSnapshotResponse:
    """Return the desktop monitor payload in one request.

    This keeps the UI on materialized/read paths and avoids separate polling for
    watchlist signals and the all-strategy priority board.
    """

    rows = _list_user_watchlist_rows(db, current_user.id)
    signals = watchlist_signal_service.build_live_signals(db, rows)
    board = low_buy_screener.priority_board(db=db, limit=priority_limit)
    return MonitorSnapshotResponse(
        updated_at=beijing_now_string(),
        watchlist_signals=signals,
        priority_board=board.model_dump(),
    )


def _list_user_watchlist_rows(db: Session, user_id: int) -> list[UserWatchlist]:
    return (
        db.execute(
            select(UserWatchlist)
            .where(UserWatchlist.user_id == user_id)
            .order_by(UserWatchlist.id.desc())
        )
        .scalars()
        .all()
    )
