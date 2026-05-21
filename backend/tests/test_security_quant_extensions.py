from __future__ import annotations

from contextlib import contextmanager
from os import environ

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import auth
from app.core.config import get_settings
from app.core.database import get_db
from app.core.rate_limit import clear_rate_limit_events
from app.models.base import Base
from app.models.entities import OperationAuditLog, User
from app.models.schema_defs.phase4 import QuantParameterRollbackRequest, QuantParameterSetCreate
from app.services.market.providers.circuit import ProviderCircuitConfig, ProviderCircuitRegistry
from app.services.quant import QuantParameterVersionService
from app.services.totp import generate_totp_code


@contextmanager
def _auth_env():
    original = environ.get("AUTH_SECRET_KEY")
    environ["AUTH_SECRET_KEY"] = "security-extensions-secret-0123456789abcdef0123456789abcdef0123456789abcdef"
    get_settings.cache_clear()
    clear_rate_limit_events()
    try:
        yield
    finally:
        if original is None:
            environ.pop("AUTH_SECRET_KEY", None)
        else:
            environ["AUTH_SECRET_KEY"] = original
        get_settings.cache_clear()
        clear_rate_limit_events()


def _session_factory():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)


def _auth_client(session_factory):
    app = FastAPI()
    app.include_router(auth.router, prefix="/api")

    def override_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    return TestClient(app)


def test_totp_mfa_blocks_plain_login_and_records_audit(monkeypatch):
    with _auth_env():
        session_factory = _session_factory()
        client = _auth_client(session_factory)
        registered = client.post(
            "/api/auth/register",
            json={"username": "mfa_user", "password": "secret123"},
        ).json()
        headers = {"Authorization": f"Bearer {registered['access_token']}"}

        setup = client.post("/api/auth/mfa/totp/setup", headers=headers)
        assert setup.status_code == 200
        setup_payload = setup.json()
        assert setup_payload["issuer"]
        assert setup_payload["account_name"] == "mfa_user"
        with session_factory() as db:
            stored_user = db.query(User).filter(User.username == "mfa_user").one()
            assert stored_user.mfa_totp_secret.startswith("enc:v1:")
            assert stored_user.mfa_totp_secret != setup_payload["secret"]
        code = generate_totp_code(setup_payload["secret"])
        enabled = client.post("/api/auth/mfa/totp/enable", headers=headers, json={"code": code})
        assert enabled.status_code == 200
        assert enabled.json()["user"]["mfa_totp_enabled"] is True

        try:
            monkeypatch.setenv("AUTH_REQUIRE_MFA_FOR_LOGIN", "true")
            get_settings.cache_clear()
            blocked = client.post("/api/auth/login", json={"username": "mfa_user", "password": "secret123"})
            assert blocked.status_code == 401
            allowed = client.post(
                "/api/auth/login",
                json={"username": "mfa_user", "password": "secret123", "mfa_code": generate_totp_code(setup_payload["secret"])},
            )
            assert allowed.status_code == 200
        finally:
            monkeypatch.delenv("AUTH_REQUIRE_MFA_FOR_LOGIN", raising=False)
            get_settings.cache_clear()
        with session_factory() as db:
            operations = [row.operation for row in db.query(OperationAuditLog).all()]
        assert "auth_mfa_enable" in operations


def test_quant_parameters_support_market_state_scope_and_paper_namespace():
    db = _session_factory()()
    service = QuantParameterVersionService(db)
    service.create(
        QuantParameterSetCreate(
            version="base-low-buy",
            scope="low_buy",
            params={"paper": {"dynamic_exit": {"enabled": True}}, "low_buy": {"min_priority_score": 70}},
        ),
        created_by="tester",
    )
    service.create(
        QuantParameterSetCreate(
            version="repair-low-buy",
            scope="low_buy",
            market_state_scope="repair",
            params={"low_buy": {"min_priority_score": 91}},
        ),
        created_by="tester",
    )

    repair = service.current(scope="low_buy", market_state_scope="repair")
    fallback = service.current(scope="low_buy", market_state_scope="fast_rotation")
    assert repair.version == "repair-low-buy"
    assert repair.market_state_scope == "repair"
    assert fallback.version == "base-low-buy"

    rolled = service.rollback(
        QuantParameterRollbackRequest(version="repair-low-buy", scope="low_buy", market_state_scope="repair"),
        operator="tester",
    )
    assert rolled.market_state_scope == "repair"


def test_provider_circuit_metrics_are_global_and_observable():
    registry = ProviderCircuitRegistry(ProviderCircuitConfig(failure_threshold=1, cooldown_seconds=30, slow_call_ms=1))
    registry.record("unit_provider", "quote", ok=False, latency_ms=5, error="timeout")
    snapshot = ProviderCircuitRegistry(ProviderCircuitConfig()).snapshot()
    key = "unit_provider:quote"

    assert snapshot["provider_calls_total"] >= 1
    assert snapshot["provider_failures_total"] >= 1
    assert snapshot["provider_slow_calls_total"] >= 1
    assert snapshot["providers"][key]["circuit_open"] is True


def test_provider_circuit_allows_single_half_open_probe():
    registry = ProviderCircuitRegistry(ProviderCircuitConfig(failure_threshold=1, cooldown_seconds=30, slow_call_ms=1000))
    provider = "unit_provider_half_open"
    operation = "quote"
    key = f"{provider}:{operation}"
    registry.record(provider, operation, ok=False, latency_ms=1, error="timeout")
    registry._states[key].opened_until = 0  # force cooldown expiry without sleeping

    assert registry.can_call(provider, operation) is True
    assert registry.can_call(provider, operation) is False
    registry.record(provider, operation, ok=True, latency_ms=1)
    assert registry.can_call(provider, operation) is True


def test_provider_circuit_uses_exponential_cooldown_sequence():
    registry = ProviderCircuitRegistry(
        ProviderCircuitConfig(
            failure_threshold=1,
            cooldown_seconds=20,
            cooldown_second_seconds=45,
            cooldown_max_seconds=90,
            slow_call_ms=1000,
        )
    )
    provider = "unit_provider_backoff"
    operation = "quote"
    key = f"{provider}:{operation}"

    registry.record(provider, operation, ok=False, latency_ms=1, error="first")
    first_remaining = registry.snapshot()["providers"][key]["cooldown_remaining_seconds"]
    registry._states[key].opened_until = 0
    registry.can_call(provider, operation)
    registry.record(provider, operation, ok=False, latency_ms=1, error="second")
    second_remaining = registry.snapshot()["providers"][key]["cooldown_remaining_seconds"]

    assert 15 <= first_remaining <= 20
    assert 40 <= second_remaining <= 45
