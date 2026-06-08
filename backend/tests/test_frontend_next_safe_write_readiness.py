from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import data_quality, runtime_tasks, screeners, strategy_tracking
from app.core.auth import get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.models.base import Base
from app.models.entities import LowBuyTradeLifecycleSnapshot, OperationAuditLog, RuntimeTask
from app.models.schema_defs.phase4 import RuntimeTaskCreate
from app.services.tasks import RuntimeTaskQueue


ADMIN_TOKEN = "test-admin-token"


def test_runtime_task_create_cancel_has_audit_permission_and_readback(monkeypatch) -> None:
    client, Session = _client(monkeypatch, runtime_only=True)
    payload = {
        "task_type": "frontend_next_smoke_noop",
        "payload": {"source": "frontend-next-test"},
        "priority": 999,
        "idempotency_key": "frontend-next-safe-write-runtime",
        "max_attempts": 1,
    }

    missing = client.post("/api/runtime-tasks", json=payload)
    invalid = client.post("/api/runtime-tasks", json=payload, headers={"X-Admin-Token": "bad-token"})
    created = client.post("/api/runtime-tasks", json=payload, headers=_admin_headers("runtimeTaskCreate", "FNX-SW-DATA-TASK"))

    assert missing.status_code == 401
    assert invalid.status_code == 403
    assert created.status_code == 200
    created_body = created.json()
    assert created_body["audit_id"]
    task_id = int(created_body["id"])

    cancelled = client.post(
        f"/api/runtime-tasks/{task_id}/cancel",
        json={"reason": "unit rollback"},
        headers=_admin_headers("runtimeTaskCreate", "FNX-SW-DATA-TASK"),
    )
    readback = client.get(f"/api/runtime-tasks/{task_id}", headers={"X-Admin-Token": ADMIN_TOKEN})

    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert readback.status_code == 200
    assert readback.json()["status"] == "cancelled"
    with Session() as db:
        audits = db.execute(select(OperationAuditLog).order_by(OperationAuditLog.id.asc())).scalars().all()
    assert [row.operation for row in audits] == ["frontend_next.runtime_task_create", "frontend_next.runtime_task_cancel"]


def test_data_quality_backfill_and_repair_enqueue_cancel_with_audit(monkeypatch) -> None:
    client, Session = _client(monkeypatch, data_only=True)
    invalid = client.post(
        "/api/data-quality/backfill",
        json={"dataset_key": "daily_bars", "scope": "all", "start_date": "2026-06-05", "end_date": "2026-06-05"},
        headers={"X-Admin-Token": "bad-token", **_safe_headers("dataQualityBackfill", "FNX-SW-DATA-TASK")},
    )
    backfill = client.post(
        "/api/data-quality/backfill",
        json={"dataset_key": "daily_bars", "scope": "all", "start_date": "2026-06-05", "end_date": "2026-06-05"},
        headers=_admin_headers("dataQualityBackfill", "FNX-SW-DATA-TASK"),
    )
    repair = client.post(
        "/api/data-quality/repair",
        json={"dataset_key": "daily_bars", "dry_run": True, "refetch": False},
        headers=_admin_headers("dataQualityRepair", "FNX-SW-DATA-REPAIR"),
    )

    assert invalid.status_code == 403
    assert backfill.status_code == 200
    assert repair.status_code == 200
    assert backfill.json()["audit_id"]
    assert repair.json()["audit_id"]
    with Session() as db:
        queue = RuntimeTaskQueue(db)
        cancelled = [queue.cancel(backfill.json()["id"], reason="unit rollback"), queue.cancel(repair.json()["id"], reason="unit rollback")]
        audits = db.execute(select(OperationAuditLog).order_by(OperationAuditLog.id.asc())).scalars().all()
        tasks = db.execute(select(RuntimeTask).order_by(RuntimeTask.id.asc())).scalars().all()

    assert [item.status for item in cancelled] == ["cancelled", "cancelled"]
    assert [row.status for row in tasks] == ["cancelled", "cancelled"]
    assert [row.operation for row in audits] == ["frontend_next.data_quality_backfill", "frontend_next.data_quality_repair"]


def test_strategy_review_record_create_delete_and_refresh_audit(monkeypatch) -> None:
    client, Session = _client(monkeypatch, strategy_only=True)
    payload = {
        "strategy_key": "n_pattern_long_wash",
        "symbol": "000001",
        "review_state": "watch",
        "notes": "unit test",
        "verdict": "review-only",
        "idempotency_key": "frontend-next-safe-write-review",
    }

    created = client.post(
        "/api/strategy-tracking/review-records",
        json=payload,
        headers=_safe_headers("strategyReviewRecord", "FNX-SW-STRATEGY-REVIEW"),
    )
    assert created.status_code == 200
    review_id = created.json()["review_id"]
    listed = client.get("/api/strategy-tracking/review-records?symbol=000001")
    deleted = client.delete(f"/api/strategy-tracking/review-records/{review_id}")
    after_delete = client.get("/api/strategy-tracking/review-records?symbol=000001")
    refresh_missing = client.post("/api/strategy-tracking/refresh?range=1")
    refresh_invalid = client.post(
        "/api/strategy-tracking/refresh?range=1",
        headers={"X-Admin-Token": "bad-token", **_safe_headers("strategyTrackingRefresh", "FNX-SW-STRATEGY-REVIEW")},
    )

    assert listed.status_code == 200
    assert any(item["review_id"] == review_id for item in listed.json()["items"])
    assert deleted.status_code == 200
    assert after_delete.status_code == 200
    assert not any(item["review_id"] == review_id for item in after_delete.json()["items"])
    assert refresh_missing.status_code == 401
    assert refresh_invalid.status_code == 403
    with Session() as db:
        audits = db.execute(select(OperationAuditLog).order_by(OperationAuditLog.id.asc())).scalars().all()
    assert [row.operation for row in audits] == ["frontend_next.strategy_review_record", "frontend_next.strategy_review_delete"]
    detail = json.loads(audits[0].detail_json)
    assert detail["strategy_boundaries"]["changed_priority_board"] is False
    assert detail["strategy_boundaries"]["changed_production_score"] is False


def test_playbook_lifecycle_and_strategy_governance_audit_hash_and_restore(monkeypatch) -> None:
    client, Session = _client(monkeypatch, screeners_only=True)
    with Session() as db:
        db.add(
            LowBuyTradeLifecycleSnapshot(
                user_scope="default",
                signal_trade_date="2026-06-05",
                strategy_key="first_board",
                symbol="000001",
                name="平安银行",
                status="planned",
                entry_plan_low=10,
                entry_plan_high=10.5,
                stop_loss=9.5,
                take_profit=11,
            )
        )
        db.commit()

    missing = client.patch(
        "/api/screeners/low-buy/strategies/first_board",
        json={"status": "paused", "reason": "unit"},
    )
    invalid = client.patch(
        "/api/screeners/low-buy/strategies/first_board",
        json={"status": "paused", "reason": "unit"},
        headers={"X-Admin-Token": "bad-token", **_safe_headers("lowBuyStrategyUpdate", "FNX-SW-PLAYBOOK-LIFECYCLE")},
    )
    changed = client.patch(
        "/api/screeners/low-buy/lifecycle/000001",
        json={"signal_trade_date": "2026-06-05", "strategy_key": "first_board", "status": "invalid"},
        headers=_admin_headers("lowBuyLifecycleUpdate", "FNX-SW-PLAYBOOK-LIFECYCLE"),
    )
    restored = client.patch(
        "/api/screeners/low-buy/lifecycle/000001",
        json={"signal_trade_date": "2026-06-05", "strategy_key": "first_board", "status": "planned"},
        headers=_admin_headers("lowBuyLifecycleUpdate", "FNX-SW-PLAYBOOK-LIFECYCLE"),
    )
    strategy = client.patch(
        "/api/screeners/low-buy/strategies/first_board",
        json={"status": "paused", "reason": "unit"},
        headers=_admin_headers("lowBuyStrategyUpdate", "FNX-SW-PLAYBOOK-LIFECYCLE"),
    )

    assert missing.status_code == 401
    assert invalid.status_code == 403
    assert changed.status_code == 200
    assert changed.json()["audit_id"]
    assert changed.json()["before_hash"] != changed.json()["after_hash"]
    assert restored.status_code == 200
    assert restored.json()["status"] == "planned"
    assert strategy.status_code == 200
    assert strategy.json()["audit_id"]
    with Session() as db:
        row = db.execute(select(LowBuyTradeLifecycleSnapshot)).scalar_one()
        audits = db.execute(select(OperationAuditLog).order_by(OperationAuditLog.id.asc())).scalars().all()
    assert row.status == "planned"
    assert [row.operation for row in audits] == [
        "frontend_next.low_buy_lifecycle_update",
        "frontend_next.low_buy_lifecycle_update",
        "frontend_next.low_buy_strategy_governance_update",
    ]


def test_playbook_lifecycle_smoke_fixture_create_update_delete(monkeypatch) -> None:
    client, Session = _client(monkeypatch, screeners_only=True)
    headers = _admin_headers("lowBuyLifecycleUpdate", "FNX-SW-PLAYBOOK-LIFECYCLE")

    created = client.post(
        "/api/screeners/low-buy/lifecycle/smoke-fixture",
        json={
            "symbol": "000001",
            "name": "平安银行",
            "strategy_key": "first_board",
            "signal_trade_date": "2026-06-05",
        },
        headers=headers,
    )
    changed = client.patch(
        "/api/screeners/low-buy/lifecycle/000001",
        json={"signal_trade_date": "2026-06-05", "strategy_key": "first_board", "status": "invalid"},
        headers=headers,
    )
    restored = client.patch(
        "/api/screeners/low-buy/lifecycle/000001",
        json={
            "signal_trade_date": "2026-06-05",
            "strategy_key": "first_board",
            "status": "planned",
            "attribution_note": "frontend-next rollback smoke fixture",
        },
        headers=headers,
    )
    deleted = client.delete(
        "/api/screeners/low-buy/lifecycle/smoke-fixture/000001?strategy_key=first_board&signal_trade_date=2026-06-05",
        headers=headers,
    )

    assert created.status_code == 200
    assert created.json()["ok"] is True
    assert changed.status_code == 200
    assert changed.json()["status"] == "invalid"
    assert restored.status_code == 200
    assert restored.json()["status"] == "planned"
    assert deleted.status_code == 200
    assert deleted.json()["deleted_count"] == 1
    with Session() as db:
        rows = db.execute(select(LowBuyTradeLifecycleSnapshot)).scalars().all()
        audits = db.execute(select(OperationAuditLog).order_by(OperationAuditLog.id.asc())).scalars().all()
    assert rows == []
    assert [row.operation for row in audits] == [
        "frontend_next.low_buy_lifecycle_smoke_fixture_create",
        "frontend_next.low_buy_lifecycle_update",
        "frontend_next.low_buy_lifecycle_update",
        "frontend_next.low_buy_lifecycle_smoke_fixture_delete",
    ]


def _client(
    monkeypatch,
    *,
    runtime_only: bool = False,
    data_only: bool = False,
    strategy_only: bool = False,
    screeners_only: bool = False,
) -> tuple[TestClient, sessionmaker]:
    monkeypatch.setenv("ADMIN_API_TOKEN", ADMIN_TOKEN)
    get_settings.cache_clear()
    Session = _session_factory()
    app = FastAPI()
    if runtime_only or not any([data_only, strategy_only, screeners_only]):
        app.include_router(runtime_tasks.router, prefix="/api")
    if data_only:
        app.include_router(data_quality.router, prefix="/api")
    if strategy_only:
        app.include_router(strategy_tracking.router, prefix="/api")
    if screeners_only:
        app.include_router(screeners.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, username="tester", is_active=True, roles="admin")

    def override_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    return TestClient(app), Session


def _session_factory() -> sessionmaker:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)


def _admin_headers(operation: str, contract_id: str) -> dict[str, str]:
    return {"X-Admin-Token": ADMIN_TOKEN, **_safe_headers(operation, contract_id)}


def _safe_headers(operation: str, contract_id: str) -> dict[str, str]:
    return {
        "X-Frontend-Next-Client-Request-Id": f"fnx-unit-{operation}",
        "X-Frontend-Next-Contract-Id": contract_id,
        "X-Frontend-Next-Contract-State": "defined_production_ready",
        "X-Frontend-Next-Operation": operation,
        "X-Frontend-Next-Source": "frontend-next",
        "X-Frontend-Next-Write-Mode": "live",
    }
