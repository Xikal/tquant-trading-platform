from __future__ import annotations

from datetime import datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import admin_users
from app.core.config import get_settings
from app.core.database import get_db
from app.models.base import Base
from app.models.entities import (
    BacktestRun,
    OperationAuditLog,
    PaperAccount,
    PaperOrder,
    TradingExperienceTradeJournalEntry,
    User,
    UserSession,
    UserWatchlist,
)


ADMIN_TOKEN = "test-admin-token"


def test_cleanup_test_users_rejects_non_test_prefix(monkeypatch) -> None:
    client, _Session = _client(monkeypatch)

    response = client.post(
        "/api/admin/users/test-cleanup",
        json={"prefixes": ["real_user_"], "dry_run": True},
        headers={"X-Admin-Token": ADMIN_TOKEN},
    )

    assert response.status_code == 400


def test_cleanup_test_users_dry_run_counts_without_delete(monkeypatch) -> None:
    client, Session = _client(monkeypatch)
    _seed_test_user(Session)

    response = client.post(
        "/api/admin/users/test-cleanup",
        json={"prefixes": ["frontend_next_smoke_"], "dry_run": True},
        headers={"X-Admin-Token": ADMIN_TOKEN},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["dry_run"] is True
    assert body["matched_users"] == 1
    assert body["matched_accounts"] == 1
    assert body["deleted_counts"]["paper_orders"] == 1
    with Session() as db:
        assert db.execute(select(User).where(User.username == "frontend_next_smoke_unit")).scalar_one_or_none() is not None


def test_cleanup_test_users_deletes_only_allowed_test_data(monkeypatch) -> None:
    client, Session = _client(monkeypatch)
    _seed_test_user(Session)
    with Session.begin() as db:
        db.add(User(username="real_user", display_name="real", password_hash="x"))

    response = client.post(
        "/api/admin/users/test-cleanup",
        json={"prefixes": ["frontend_next_smoke_"], "dry_run": False},
        headers={"X-Admin-Token": ADMIN_TOKEN},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["dry_run"] is False
    assert body["matched_users"] == 1
    with Session() as db:
        assert db.execute(select(User).where(User.username == "frontend_next_smoke_unit")).scalar_one_or_none() is None
        assert db.execute(select(User).where(User.username == "real_user")).scalar_one_or_none() is not None
        assert db.execute(select(PaperOrder)).scalar_one_or_none() is None
        assert db.execute(select(UserSession)).scalar_one_or_none() is None
        assert db.execute(select(UserWatchlist)).scalar_one_or_none() is None
        assert db.execute(select(TradingExperienceTradeJournalEntry)).scalar_one_or_none() is None
        assert db.execute(select(BacktestRun)).scalar_one_or_none() is None
        audit = db.execute(select(OperationAuditLog)).scalar_one()
        assert audit.user_id is None
        assert audit.resource_id == "frontend_next_smoke_unit"


def _client(monkeypatch) -> tuple[TestClient, sessionmaker]:
    monkeypatch.setenv("ADMIN_API_TOKEN", ADMIN_TOKEN)
    get_settings.cache_clear()
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)
    app = FastAPI()
    app.include_router(admin_users.router, prefix="/api")

    def override_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    return TestClient(app), Session


def _seed_test_user(Session: sessionmaker) -> None:
    with Session.begin() as db:
        user = User(username="frontend_next_smoke_unit", display_name="smoke", password_hash="x")
        db.add(user)
        db.flush()
        account = PaperAccount(user_id=user.id)
        db.add(account)
        db.flush()
        db.add_all(
            [
                UserSession(user_id=user.id, refresh_token_hash="hash", device_name="unit", expires_at=datetime(2099, 1, 1)),
                UserWatchlist(user_id=user.id, symbol="000001", name="平安银行"),
                TradingExperienceTradeJournalEntry(user_id=user.id, account_id=account.id, symbol="000001", action="note"),
                BacktestRun(owner_user_id=user.id, name="frontend-next rollback smoke"),
                OperationAuditLog(user_id=user.id, operation="frontend_next.unit", resource_id=user.username),
                PaperOrder(account_id=account.id, symbol="000001", name="平安银行", side="buy", quantity=100),
            ]
        )
