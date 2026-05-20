from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import research
from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.base import Base
from app.models.entities import BacktestRun


def test_legacy_research_backtest_runs_are_owner_scoped() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as db:
        db.add_all(
            [
                BacktestRun(id=1, name="mine", owner_user_id=1, result_json="{}"),
                BacktestRun(id=2, name="other", owner_user_id=2, result_json="{}"),
                BacktestRun(id=3, name="orphan", owner_user_id=None, result_json="{}"),
            ]
        )
        db.commit()

    state = {"user": SimpleNamespace(id=1, username="alice", roles="", is_active=True)}
    app = FastAPI()
    app.include_router(research.router, prefix="/api")

    def override_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: state["user"]
    client = TestClient(app)

    listed = client.get("/api/backtests/runs")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["runs"]] == [1]

    assert client.get("/api/backtests/runs/2").status_code == 404
    assert client.get("/api/backtests/runs/3").status_code == 404

    state["user"] = SimpleNamespace(id=99, username="admin", roles="admin", is_active=True)
    admin_list = client.get("/api/backtests/runs")
    assert admin_list.status_code == 200
    assert [item["id"] for item in admin_list.json()["runs"]] == [3, 2, 1]
    assert client.get("/api/backtests/runs/2").status_code == 200
