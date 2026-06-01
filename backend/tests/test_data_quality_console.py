from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import data_quality, instruments
from app.core.auth import get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.models.base import Base
from app.models.entities import DailyBarSnapshot, DataQualitySnapshot, Instrument
from app.models.schema_defs.phase4 import DataSourceProbeResponse, DataSourceQualityOut, RuntimeTaskCreate
from app.services.tasks import RuntimeTaskQueue
from app.services.tasks.analytics_handlers import register_analytics_handlers
from app.services.tasks.registry import TaskHandlerRegistry
from app.services.tasks.worker import RuntimeTaskWorker
import app.services.tasks.worker as worker_module


def test_coverage_endpoint_returns_missing_dates_and_symbol_details() -> None:
    client, Session = _client()
    with Session() as db:
        db.add_all(
            [
                Instrument(symbol="600000", name="浦发银行", market="CN", instrument_type="stock", status="active"),
                Instrument(symbol="000001", name="平安银行", market="CN", instrument_type="stock", status="active"),
                _daily_bar("600000", date(2026, 5, 25)),
                _daily_bar("000001", date(2026, 5, 25)),
                DataQualitySnapshot(
                    dataset_key="daily_bars",
                    as_of_date=date(2026, 5, 26),
                    scope="all",
                    expected_days=2,
                    actual_days=1,
                    missing_days=1,
                    invalid_rows=0,
                    duplicate_rows=0,
                    stale=False,
                    coverage_pct=50.0,
                    status="fail",
                    blockers_json=json.dumps(["daily_bars_trade_days_below_expected"], ensure_ascii=False),
                ),
            ]
        )
        db.commit()

    response = client.get("/api/data-quality/coverage?dataset_key=daily_bars&scope=all")

    assert response.status_code == 200
    payload = response.json()
    assert payload["dataset_key"] == "daily_bars"
    assert payload["scope"] == "all"
    assert payload["missing_dates"] == ["2026-05-26"]
    missing_by_symbol = {item["symbol"]: item for item in payload["missing_symbols"]}
    assert missing_by_symbol["600000"] == {"symbol": "600000", "name": "浦发银行", "missing_days": 1}
    assert missing_by_symbol["000001"] == {"symbol": "000001", "name": "平安银行", "missing_days": 1}


def test_backfill_endpoint_requires_admin_and_only_enqueues_task(monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_API_TOKEN", "test-admin-token")
    get_settings.cache_clear()
    client, Session = _client()
    payload = {
        "dataset_key": "daily_bars",
        "scope": "all",
        "start_date": "2026-05-01",
        "end_date": "2026-05-29",
    }

    rejected = client.post("/api/data-quality/backfill", json=payload)
    accepted = client.post("/api/data-quality/backfill", json=payload, headers={"X-Admin-Token": "test-admin-token"})

    assert rejected.status_code == 401
    assert accepted.status_code == 200
    body = accepted.json()
    assert body["task_type"] == "data_quality_backfill"
    assert body["status"] == "queued"
    assert body["payload"] == payload
    with Session() as db:
        tasks = RuntimeTaskQueue(db).list(limit=10).items
        daily_rows = db.execute(select(DailyBarSnapshot)).scalars().all()
    assert [item.task_type for item in tasks] == ["data_quality_backfill"]
    assert daily_rows == []


def test_trade_gate_returns_green_yellow_and_red_with_reasons(monkeypatch) -> None:
    green_client, green_session = _client()
    _patch_source_probe(monkeypatch, ok=True, quality="ok")
    with green_session() as db:
        _add_trade_gate_snapshots(db, status="ok", stale=False, blockers=[])

    green = green_client.get("/api/data-quality/trade-gate")

    assert green.status_code == 200
    green_payload = green.json()
    assert green_payload["ok"] is True
    assert {item["severity"] for item in green_payload["checks"]} == {"green"}

    yellow_client, yellow_session = _client()
    with yellow_session() as db:
        _add_trade_gate_snapshots(db, status="ok", stale=True, blockers=[])

    yellow = yellow_client.get("/api/data-quality/trade-gate")

    assert yellow.status_code == 200
    yellow_payload = yellow.json()
    assert yellow_payload["ok"] is True
    stale_check = next(item for item in yellow_payload["checks"] if item["key"] == "freshness")
    assert stale_check["severity"] == "yellow"
    assert "偏旧" in stale_check["detail"]

    red_client, red_session = _client()
    _patch_source_probe(monkeypatch, ok=False, quality="failed", warning="source offline")
    with red_session() as db:
        _add_trade_gate_snapshots(db, status="fail", stale=False, blockers=["daily_bars_trade_days_below_expected"])

    red = red_client.get("/api/data-quality/trade-gate")

    assert red.status_code == 200
    red_payload = red.json()
    assert red_payload["ok"] is False
    red_checks = [item for item in red_payload["checks"] if item["severity"] == "red"]
    assert red_checks
    assert any("daily_bars_trade_days_below_expected" in item["detail"] for item in red_checks)
    assert any(item["key"] == "source" and "source offline" in item["detail"] for item in red_checks)


def test_data_quality_backfill_task_is_registered_and_worker_consumable(monkeypatch) -> None:
    session_factory = _session_factory()
    monkeypatch.setattr(worker_module, "SessionLocal", session_factory)
    calls: list[list[str]] = []

    def fake_run(command, **_kwargs):
        calls.append([str(item) for item in command])

        class Completed:
            returncode = 0
            stdout = "ok"
            stderr = ""

        return Completed()

    monkeypatch.setattr("app.services.tasks.analytics_handlers.subprocess.run", fake_run)
    registry = TaskHandlerRegistry()
    register_analytics_handlers(registry)
    assert "data_quality_backfill" in registry.task_types()
    with session_factory() as db:
        task = RuntimeTaskQueue(db).enqueue(
            RuntimeTaskCreate(
                task_type="data_quality_backfill",
                payload={
                    "dataset_key": "daily_bars",
                    "scope": "all",
                    "start_date": "2026-05-01",
                    "end_date": "2026-05-29",
                },
                max_attempts=1,
            )
        )

    worker = RuntimeTaskWorker(registry=registry, worker_id="data-console-test", poll_interval_seconds=0.1)

    assert worker.run_once() is True
    with session_factory() as db:
        finished = RuntimeTaskQueue(db).get(task.id)
    assert finished.status == "succeeded"
    assert finished.result["status"] == "completed"
    assert calls
    assert "backfill_daily_history.py" in " ".join(calls[0])
    assert "--start-date" in calls[0]
    assert "--end-date" in calls[0]


def test_instrument_sync_requires_admin_token(monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_API_TOKEN", "test-admin-token")
    get_settings.cache_clear()
    fake_status = _FakeInstrumentSyncStatus()
    monkeypatch.setattr(instruments, "sync_status", fake_status)
    Session = _session_factory()
    app = FastAPI()
    app.include_router(instruments.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, username="tester", is_active=True)

    def override_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)

    rejected = client.post("/api/instruments/sync")
    accepted = client.post("/api/instruments/sync", headers={"X-Admin-Token": "test-admin-token"})

    assert rejected.status_code == 401
    assert accepted.status_code == 200
    assert accepted.json()["status"]["status"] == "queued"
    with Session() as db:
        tasks = RuntimeTaskQueue(db).list(limit=10).items
    assert [item.task_type for item in tasks] == ["instrument_sync"]


def _client() -> tuple[TestClient, sessionmaker]:
    Session = _session_factory()
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


class _FakeInstrumentSyncStatus:
    def __init__(self) -> None:
        self.payload = {
            "run_id": "unit-test-run",
            "kind": "all",
            "status": "idle",
            "progress_pct": 0,
            "message": "",
            "result": {},
            "error": "",
            "task_id": None,
            "updated_at": "2026-06-01T00:00:00+08:00",
        }

    def start(self, *, kind: str) -> str:
        self.payload = {**self.payload, "kind": kind, "status": "queued"}
        return str(self.payload["run_id"])

    def update(self, **payload) -> None:
        self.payload = {**self.payload, **payload}

    def fail(self, **payload) -> None:
        self.payload = {**self.payload, **payload, "status": "failed"}

    def get(self, run_id: str | None = None) -> dict[str, object]:
        return dict(self.payload)


def _session_factory() -> sessionmaker:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)


def _add_trade_gate_snapshots(db, *, status: str, stale: bool, blockers: list[str]) -> None:
    for dataset_key in ("daily_bars", "minute_bars", "tick_trades"):
        db.add(
            DataQualitySnapshot(
                dataset_key=dataset_key,
                as_of_date=date(2026, 5, 29),
                scope="production_universe",
                expected_days=1,
                actual_days=1 if status == "ok" else 0,
                missing_days=0 if status == "ok" else 1,
                invalid_rows=0,
                duplicate_rows=0,
                stale=stale,
                coverage_pct=100.0 if status == "ok" else 0.0,
                status=status,
                blockers_json=json.dumps(blockers, ensure_ascii=False),
            )
        )
    db.commit()


def _patch_source_probe(monkeypatch, *, ok: bool, quality: str, warning: str = "") -> None:
    class Probe:
        def probe(self) -> DataSourceProbeResponse:
            return DataSourceProbeResponse(
                updated_at="2026-05-29T15:30:00+08:00",
                provider_order=["unit-test-source"],
                items=[
                    DataSourceQualityOut(
                        source="unit-test-source",
                        ok=ok,
                        quality=quality,
                        latency_ms=12,
                        is_stale=False,
                        warning=warning,
                    )
                ],
                summary="unit-test",
            )

    monkeypatch.setattr(data_quality, "DataSourceProbeService", Probe, raising=False)


def _daily_bar(symbol: str, trade_date: date) -> DailyBarSnapshot:
    return DailyBarSnapshot(
        symbol=symbol,
        market="CN",
        instrument_type="stock",
        trade_date=trade_date,
        open_price=10.0,
        close_price=10.2,
        high_price=10.5,
        low_price=9.8,
        volume=1000,
        amount=10000,
        pct_chg=1.0,
        source="unit-test",
        data_quality="ok",
    )
