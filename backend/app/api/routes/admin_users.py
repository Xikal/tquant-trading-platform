from __future__ import annotations

from datetime import datetime
from typing import Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.orm import Session

from app.core.admin_auth import require_admin_auth
from app.core.database import get_db
from app.core.timezone import utc_now_naive
from app.models.agent_notification_risk_entities import AgentAuditLog, NotificationEvent, PaperAgentRun, RiskEvent, SseSubscription
from app.models.auth_system_entities import UserFeishuBinding, UserSectorExclusion
from app.models.backtest_entities import BacktestOptimization, BacktestValidation
from app.core.user_permissions import paper_trade_enabled
from app.models.entities import (
    BacktestRun,
    OperationAuditLog,
    PaperAccount,
    PaperDailyReport,
    PaperMarketPerfDaily,
    PaperOrder,
    PaperPerformanceSnapshot,
    PaperPosition,
    PaperPositionLot,
    PaperReviewReport,
    PaperStrategyPerfDaily,
    PaperTrade,
    PaperTradeTag,
    TradingExperienceTradeJournalEntry,
    User,
    UserSession,
    UserWatchlist,
)

router = APIRouter(prefix="/admin/users")


class AdminUserOut(BaseModel):
    id: int
    username: str
    display_name: str = ""
    is_active: bool = True
    can_paper_trade: bool = True
    roles: list[str] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AdminUsersResponse(BaseModel):
    users: list[AdminUserOut]


class AdminUserUpdate(BaseModel):
    display_name: Optional[str] = Field(default=None, max_length=64)
    is_active: Optional[bool] = None
    can_paper_trade: Optional[bool] = None
    roles: Optional[Union[list[str], str]] = None


class AdminTestUserCleanupRequest(BaseModel):
    prefixes: list[str] = Field(default_factory=list)
    dry_run: bool = True
    reason: str = Field(default="", max_length=160)


class AdminTestUserCleanupResponse(BaseModel):
    ok: bool
    dry_run: bool
    matched_users: int
    matched_accounts: int
    deleted_counts: dict[str, int] = Field(default_factory=dict)


@router.get("", response_model=AdminUsersResponse)
def list_users(
    q: str = Query(default="", max_length=64),
    limit: int = Query(default=100, ge=1, le=500),
    _: None = Depends(require_admin_auth),
    db: Session = Depends(get_db),
) -> AdminUsersResponse:
    statement = select(User).order_by(User.id.desc()).limit(limit)
    keyword = q.strip()
    if keyword:
        like_text = f"%{keyword}%"
        statement = (
            select(User)
            .where(or_(User.username.like(like_text), User.display_name.like(like_text)))
            .order_by(User.id.desc())
            .limit(limit)
        )
    rows = db.execute(statement).scalars().all()
    return AdminUsersResponse(users=[_user_out(row) for row in rows])


@router.post("/test-cleanup", response_model=AdminTestUserCleanupResponse)
def cleanup_test_users(
    payload: AdminTestUserCleanupRequest,
    _: None = Depends(require_admin_auth),
    db: Session = Depends(get_db),
) -> AdminTestUserCleanupResponse:
    prefixes = _validated_cleanup_prefixes(payload.prefixes)
    users = db.execute(
        select(User).where(or_(*(User.username.like(f"{prefix}%") for prefix in prefixes))).order_by(User.id.asc())
    ).scalars().all()
    user_ids = [int(user.id) for user in users]
    account_ids = _paper_account_ids_for_users(db, user_ids)
    counts = _cleanup_counts(db, user_ids=user_ids, account_ids=account_ids)
    if not payload.dry_run and user_ids:
        _delete_test_user_data(db, user_ids=user_ids, account_ids=account_ids)
        db.commit()
    return AdminTestUserCleanupResponse(
        ok=True,
        dry_run=payload.dry_run,
        matched_users=len(user_ids),
        matched_accounts=len(account_ids),
        deleted_counts=counts,
    )


@router.put("/{user_id}", response_model=AdminUserOut)
def update_user(
    user_id: int,
    payload: AdminUserUpdate,
    _: None = Depends(require_admin_auth),
    db: Session = Depends(get_db),
) -> AdminUserOut:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    should_revoke_sessions = False
    if payload.display_name is not None:
        user.display_name = payload.display_name.strip()
    if payload.is_active is not None and payload.is_active != user.is_active:
        user.is_active = payload.is_active
        should_revoke_sessions = True
    if payload.can_paper_trade is not None and payload.can_paper_trade != user.can_paper_trade:
        user.can_paper_trade = payload.can_paper_trade
        should_revoke_sessions = True
    if payload.roles is not None:
        roles_text = _roles_to_text(payload.roles)
        if roles_text != (user.roles or ""):
            user.roles = roles_text
            should_revoke_sessions = True
    if should_revoke_sessions:
        user.token_version = int(getattr(user, "token_version", 0) or 0) + 1
        _revoke_user_sessions(db, user.id)
    db.commit()
    db.refresh(user)
    return _user_out(user)


def _revoke_user_sessions(db: Session, user_id: int) -> None:
    db.execute(
        UserSession.__table__.update()
        .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
        .values(revoked_at=utc_now_naive())
    )


def _roles_to_text(value: Union[list[str], str]) -> str:
    if isinstance(value, str):
        return ",".join(item.strip() for item in value.split(",") if item.strip())
    return ",".join(str(item).strip() for item in value if str(item).strip())


def _user_out(user: User) -> AdminUserOut:
    roles = [item.strip() for item in (user.roles or "").split(",") if item.strip()]
    return AdminUserOut(
        id=user.id,
        username=user.username,
        display_name=user.display_name or user.username,
        is_active=user.is_active,
        can_paper_trade=paper_trade_enabled(user.can_paper_trade),
        roles=roles,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


def _validated_cleanup_prefixes(prefixes: list[str]) -> list[str]:
    allowed = ("frontend_next_smoke_", "frontend_next_shadow_", "perf_gate_")
    cleaned = [item.strip() for item in prefixes if item and item.strip()]
    if not cleaned:
        cleaned = list(allowed)
    invalid = [item for item in cleaned if not any(item.startswith(prefix) for prefix in allowed)]
    if invalid:
        raise HTTPException(status_code=400, detail="只允许清理 frontend_next_smoke_/frontend_next_shadow_/perf_gate_ 测试账号前缀")
    return cleaned


def _paper_account_ids_for_users(db: Session, user_ids: list[int]) -> list[int]:
    if not user_ids:
        return []
    return [
        int(item)
        for item in db.execute(select(PaperAccount.id).where(PaperAccount.user_id.in_(user_ids))).scalars().all()
    ]


def _cleanup_counts(db: Session, *, user_ids: list[int], account_ids: list[int]) -> dict[str, int]:
    return {
        "users": len(user_ids),
        "paper_accounts": len(account_ids),
        "user_sessions": _count_rows(db, UserSession, UserSession.user_id, user_ids),
        "user_watchlists": _count_rows(db, UserWatchlist, UserWatchlist.user_id, user_ids),
        "trade_journal": _count_rows(db, TradingExperienceTradeJournalEntry, TradingExperienceTradeJournalEntry.user_id, user_ids),
        "backtest_runs": _count_rows(db, BacktestRun, BacktestRun.owner_user_id, user_ids),
        "backtest_validations": _count_rows(db, BacktestValidation, BacktestValidation.owner_user_id, user_ids),
        "backtest_optimizations": _count_rows(db, BacktestOptimization, BacktestOptimization.owner_user_id, user_ids),
        "operation_audit_log": _count_rows(db, OperationAuditLog, OperationAuditLog.user_id, user_ids),
        "paper_orders": _count_rows(db, PaperOrder, PaperOrder.account_id, account_ids),
        "paper_trades": _count_rows(db, PaperTrade, PaperTrade.account_id, account_ids),
    }


def _count_rows(db: Session, model, column, values: list[int]) -> int:
    if not values:
        return 0
    return int(db.execute(select(func.count()).select_from(model).where(column.in_(values))).scalar_one() or 0)


def _delete_test_user_data(db: Session, *, user_ids: list[int], account_ids: list[int]) -> None:
    if account_ids:
        _delete_where_in(db, PaperAgentRun, PaperAgentRun.account_id, account_ids)
        _delete_where_in(db, RiskEvent, RiskEvent.account_id, account_ids)
        _delete_where_in(db, PaperDailyReport, PaperDailyReport.account_id, account_ids)
        _delete_where_in(db, PaperReviewReport, PaperReviewReport.account_id, account_ids)
        _delete_where_in(db, PaperStrategyPerfDaily, PaperStrategyPerfDaily.account_id, account_ids)
        _delete_where_in(db, PaperMarketPerfDaily, PaperMarketPerfDaily.account_id, account_ids)
        _delete_where_in(db, PaperPerformanceSnapshot, PaperPerformanceSnapshot.account_id, account_ids)
        _delete_where_in(db, TradingExperienceTradeJournalEntry, TradingExperienceTradeJournalEntry.account_id, account_ids)
        _delete_where_in(db, PaperTradeTag, PaperTradeTag.account_id, account_ids)
        _delete_where_in(db, PaperPositionLot, PaperPositionLot.account_id, account_ids)
        _delete_where_in(db, PaperPosition, PaperPosition.account_id, account_ids)
        _delete_where_in(db, PaperTrade, PaperTrade.account_id, account_ids)
        _delete_where_in(db, PaperOrder, PaperOrder.account_id, account_ids)
        _delete_where_in(db, PaperAccount, PaperAccount.id, account_ids)
    if user_ids:
        _delete_where_in(db, AgentAuditLog, AgentAuditLog.user_id, user_ids)
        _delete_where_in(db, NotificationEvent, NotificationEvent.user_id, user_ids)
        _delete_where_in(db, SseSubscription, SseSubscription.user_id, user_ids)
        _delete_where_in(db, UserFeishuBinding, UserFeishuBinding.user_id, user_ids)
        _delete_where_in(db, UserSectorExclusion, UserSectorExclusion.user_id, user_ids)
        _delete_where_in(db, TradingExperienceTradeJournalEntry, TradingExperienceTradeJournalEntry.user_id, user_ids)
        _delete_where_in(db, UserWatchlist, UserWatchlist.user_id, user_ids)
        _delete_where_in(db, BacktestRun, BacktestRun.owner_user_id, user_ids)
        _delete_where_in(db, BacktestValidation, BacktestValidation.owner_user_id, user_ids)
        _delete_where_in(db, BacktestOptimization, BacktestOptimization.owner_user_id, user_ids)
        db.execute(update(OperationAuditLog).where(OperationAuditLog.user_id.in_(user_ids)).values(user_id=None))
        _delete_where_in(db, UserSession, UserSession.user_id, user_ids)
        _delete_where_in(db, User, User.id, user_ids)


def _delete_where_in(db: Session, model, column, values: list[int]) -> None:
    if values:
        db.execute(delete(model).where(column.in_(values)))
