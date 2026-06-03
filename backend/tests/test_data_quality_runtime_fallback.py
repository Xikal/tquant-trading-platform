from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import data_quality
from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.base import Base


def test_runtime_fallback_route_reports_missing_worker_heartbeat() -> None:
    client, _Session = _client()

    response = client.get("/api/data-quality/runtime-fallback")

    assert response.status_code == 200
    body = response.json()
    assert body["worker_status"] == "missing"
    assert body["blocking"] is True
    assert body["critical_queued_count"] == 0
    assert "runtime worker heartbeat missing" == body["message"]


def _client() -> tuple[TestClient, sessionmaker]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)
    app = FastAPI()
    app.include_router(data_quality.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, username="tester", is_active=True)

    def override_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    return TestClient(app), Session
