from __future__ import annotations

from datetime import datetime, time as datetime_time
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import PaperAccount, PaperOrder, PaperPosition, User
from app.services.paper.scheduler_helpers import _beijing_now_naive, _blocking_account_ids


def get_active_account(db: Session) -> PaperAccount | None:
    accounts = get_active_accounts(db)
    return accounts[0] if accounts else None


def get_active_accounts(db: Session) -> list[PaperAccount]:
    accounts = (
        db.execute(
            select(PaperAccount)
            .outerjoin(User, PaperAccount.user_id == User.id)
            .where(PaperAccount.status.in_(["active", "paused"]))
            .where(
                (PaperAccount.user_id.is_(None))
                | ((User.is_active.is_(True)) & (User.can_paper_trade.is_(True)))
            )
            .order_by(PaperAccount.id.asc())
        )
        .scalars()
        .all()
    )
    activate_auto_managed_accounts(db, accounts)
    return accounts


def get_account(db: Session, *, account_id: int) -> PaperAccount | None:
    account = db.execute(
        select(PaperAccount)
        .where(PaperAccount.id == account_id)
        .where(PaperAccount.status.in_(["active", "paused"]))
    ).scalar_one_or_none()
    activate_auto_managed_accounts(db, [account] if account else [])
    return account


def activate_auto_managed_accounts(db: Session, accounts: list[PaperAccount]) -> None:
    blocked_ids = _blocking_account_ids(db, [account.id for account in accounts])
    changed = False
    for account in accounts:
        if account.id in blocked_ids:
            continue
        if account.status == "paused":
            account.status = "active"
            db.add(account)
            changed = True
    if changed:
        db.commit()


def get_positions_summary(db: Session, account: PaperAccount) -> list[dict[str, Any]]:
    rows = db.execute(
        select(PaperPosition).where(PaperPosition.account_id == account.id, PaperPosition.quantity > 0)
    ).scalars().all()
    total_assets = max(float(account.total_assets or 0), 1.0)
    now = _beijing_now_naive()
    return [
        {
            "symbol": row.symbol,
            "hold_days": max((now - row.opened_at).days, 0) if row.opened_at else 0,
            "position_pct": float(row.market_value or 0) / total_assets * 100,
            "market_value": float(row.market_value or 0),
        }
        for row in rows
    ]


def get_today_orders(db: Session, account_id: int) -> list[dict[str, Any]]:
    start = datetime.combine(_beijing_now_naive().date(), datetime_time.min)
    rows = db.execute(
        select(PaperOrder).where(
            PaperOrder.account_id == account_id,
            PaperOrder.created_at >= start,
        )
    ).scalars().all()
    return [{"symbol": row.symbol, "status": row.status, "side": row.side, "source": row.source} for row in rows]
