from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import internal_scan_worker
from app.core.config import get_settings
from app.core.database import get_db
from app.models.base import Base
from app.models.entities import RuntimeTask


def test_internal_scan_worker_run_returns_accepted_job(monkeypatch):
    monkeypatch.setenv("TQUANT_INTERNAL_SERVICE_TOKEN", "test-token")
    get_settings.cache_clear()
    engine = create_engine("sqlite://", future=True, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)

    app = FastAPI()
    app.include_router(internal_scan_worker.router, prefix="/api")

    def _db_override():
        with Session() as db:
            yield db

    app.dependency_overrides[get_db] = _db_override
    client = TestClient(app)

    try:
        response = client.get(
            "/api/internal/scan-worker/v1/run?strategies=first_board&scan_limit=12&limit=5",
            headers={"X-Internal-Service-Token": "test-token"},
        )

        assert response.status_code == 202
        payload = response.json()
        assert payload["ok"] is True
        assert payload["accepted"] is True
        assert payload["status"] == "accepted"
        assert payload["job_id"]
        assert payload["strategy_engine"] == "python_reference"
        assert payload["production_write_enabled"] is True
        with Session() as db:
            task = db.get(RuntimeTask, int(payload["job_id"]))
            assert task is not None
            assert len(task.idempotency_key) <= 160
    finally:
        get_settings.cache_clear()
