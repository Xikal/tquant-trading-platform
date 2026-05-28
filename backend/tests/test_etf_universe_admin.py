from __future__ import annotations

from os import environ
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import market
from app.core.auth import get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.models.base import Base
from app.models.entities import OperationAuditLog, QuantParameterAuditLog
from app.services.etf.universe_admin import EtfUniverseAdminService


def _admin_user() -> SimpleNamespace:
    return SimpleNamespace(id=1, username="admin", roles="admin", is_active=True)


def _make_client():
    environ["ADMIN_API_TOKEN"] = "test-admin-token"
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
    app.include_router(market.router, prefix="/api")

    def override_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = _admin_user
    return TestClient(app), Session


def test_etf_universe_admin_requires_admin_token() -> None:
    client, _Session = _make_client()

    response = client.get("/api/market/etf-universe/admin")

    assert response.status_code == 401


def test_etf_universe_admin_returns_diff_and_validation() -> None:
    client, _Session = _make_client()

    response = client.post(
        "/api/market/etf-universe/validate",
        headers={"X-Admin-Token": "test-admin-token"},
        json={
            "draft_overrides": {
                "159999": {
                    "symbol": "159999",
                    "name": "测试行业ETF",
                    "category": "sector",
                    "t0_eligible": True,
                    "settlement_rule": "t1",
                    "min_amount": -1,
                    "max_spread_bps": 60,
                    "slippage_bps": 40,
                    "enabled_for_t0": True,
                    "notes": "",
                }
            }
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["validation"]["error_count"] >= 2
    fields = {item["field"] for item in body["validation"]["issues"]}
    assert {"settlement_rule", "min_amount", "notes"} <= fields
    assert any(item["risk_level"] == "high" for item in body["diff"])


def test_etf_universe_apply_writes_quant_and_operation_audit() -> None:
    client, Session = _make_client()
    draft = {
        "518880": {
            "symbol": "518880",
            "name": "黄金ETF",
            "category": "gold",
            "t0_eligible": True,
            "settlement_rule": "t0",
            "min_amount": 40_000_000,
            "max_spread_bps": 9,
            "slippage_bps": 4,
            "premium_discount_available": True,
            "enabled_for_t0": True,
            "notes": "测试 universe 管理保存。",
        }
    }

    response = client.post(
        "/api/market/etf-universe/apply",
        headers={"X-Admin-Token": "test-admin-token"},
        json={
            "draft_overrides": draft,
            "version": "etf-universe-test-v1",
            "description": "测试 ETF universe 管理保存",
            "activate": True,
            "confirm_high_risk": True,
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["version"] == "etf-universe-test-v1"
    with Session() as db:
        quant_audit_count = db.query(QuantParameterAuditLog).count()
        operation_audit = db.query(OperationAuditLog).filter(OperationAuditLog.operation == "etf_universe_apply").one_or_none()
    assert quant_audit_count >= 1
    assert operation_audit is not None
    assert operation_audit.resource_id == "etf-universe-test-v1"


def test_etf_universe_rollback_restores_previous_version() -> None:
    client, Session = _make_client()
    with Session() as db:
        service = EtfUniverseAdminService(db)
        service.apply(
            draft_overrides={},
            version="etf-universe-base-test",
            description="baseline",
            activate=True,
            confirm_high_risk=True,
            user=_admin_user(),
        )
        service.apply(
            draft_overrides={
                "518880": {
                    "symbol": "518880",
                    "name": "黄金ETF",
                    "category": "gold",
                    "t0_eligible": True,
                    "settlement_rule": "t0",
                    "min_amount": 33_000_000,
                    "max_spread_bps": 9,
                    "slippage_bps": 4,
                    "premium_discount_available": True,
                    "enabled_for_t0": True,
                    "notes": "temporary override",
                }
            },
            version="etf-universe-temp-test",
            description="temp",
            activate=True,
            confirm_high_risk=True,
            user=_admin_user(),
        )

    response = client.post(
        "/api/market/etf-universe/rollback",
        headers={"X-Admin-Token": "test-admin-token"},
        json={"version": "etf-universe-base-test", "confirm": True},
    )

    assert response.status_code == 200, response.text
    assert response.json()["version"] == "etf-universe-base-test"
    body = client.get("/api/market/etf-universe/admin", headers={"X-Admin-Token": "test-admin-token"}).json()
    assert body["version"] == "etf-universe-v1"
    assert body["override_count"] == 0
