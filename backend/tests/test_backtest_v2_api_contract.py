from __future__ import annotations

import threading
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.base import Base
from app.models.entities import BacktestDailySnapshot, BacktestRun, BacktestTrade
from app.models.schema_defs.backtest import BacktestRunCreate
from app.services.backtest.data_provider import DataQualityReport
from app.services.backtest.engine import BacktestOrder, BacktestResult
from app.services.backtest.persistence import BacktestResultPersistence
from app.services.backtest.portfolio import RealizedTrade
from app.services.backtest_job_service import BacktestJobService

backtests_route = pytest.importorskip(
    "app.api.routes.backtests",
    reason="Backtest v2 route module app.api.routes.backtests is not implemented yet.",
)


class _BacktestServiceStub:
    def __init__(self) -> None:
        self.submitted_payload: dict[str, Any] | None = None
        self.cancelled_run_id: int | None = None

    def create_run(self, payload, owner_user_id: int | None):  # noqa: ANN001
        self.submitted_payload = _dump(payload)
        return {
            "id": 42,
            "name": self.submitted_payload.get("name") or "first_board portfolio test",
            "status": "queued",
            "strategy_keys": self.submitted_payload.get("strategy_keys", []),
            "start_date": self.submitted_payload.get("start_date"),
            "end_date": self.submitted_payload.get("end_date"),
            "initial_cash": self.submitted_payload.get("initial_cash", 0.0),
            "final_equity": self.submitted_payload.get("initial_cash", 0.0),
            "progress_pct": 0.0,
            "benchmark_symbol": self.submitted_payload.get("benchmark_symbol", ""),
            "owner_user_id": owner_user_id,
            "created_at": "2026-05-05T09:30:00+08:00",
            "params": self.submitted_payload.get("params", {}),
            "result": {},
            "dataset_manifest_id": self.submitted_payload.get("dataset_manifest_id"),
            "engine_version": self.submitted_payload.get("engine_version", "backtest-v2"),
            "strategy_version": self.submitted_payload.get("strategy_version", ""),
            "data_version": self.submitted_payload.get("data_version", ""),
            "fee_model_version": self.submitted_payload.get("fee_model_version", ""),
            "slippage_bps": self.submitted_payload.get("slippage_bps", 0.0),
            "error_message": "",
        }

    def list_runs(
        self,
        *,
        owner_user_id: int | None,
        is_admin: bool,
        limit=20,
        offset=0,
        status_filter=None,
        strategy_key=None,
    ):  # noqa: ANN001, ARG002
        return {
            "items": [
                {
                    "id": 42,
                    "name": "first_board portfolio test",
                    "status": "succeeded",
                    "strategy_keys": ["first_board"],
                    "start_date": "2025-01-02",
                    "end_date": "2026-04-30",
                    "initial_cash": 500000.0,
                    "final_equity": 541000.0,
                    "progress_pct": 100.0,
                    "benchmark_symbol": "000300",
                    "owner_user_id": owner_user_id,
                    "created_at": "2026-05-05T09:30:00+08:00",
                }
            ],
            "total": 1,
            "limit": limit,
            "offset": offset,
        }

    def get_run(self, run_id: int, *, owner_user_id: int | None, is_admin: bool):  # noqa: ANN001, ARG002
        if run_id == 403:
            raise HTTPException(status_code=403, detail="Forbidden")
        return {
            "id": run_id,
            "name": "first_board portfolio test",
            "status": "succeeded",
            "strategy_keys": ["first_board"],
            "start_date": "2025-01-02",
            "end_date": "2026-04-30",
            "initial_cash": 500000.0,
            "final_equity": 541000.0,
            "progress_pct": 100.0,
            "benchmark_symbol": "000300",
            "owner_user_id": owner_user_id,
            "created_at": "2026-05-05T09:30:00+08:00",
            "params": {"execution_model": "open_price"},
            "result": {
                "metrics": {
                    "total_return_pct": 8.2,
                    "sharpe_ratio": 1.35,
                    "sortino_ratio": 1.91,
                    "calmar_ratio": 2.0,
                    "benchmark_alpha_pct": 3.1,
                    "information_ratio": 0.72,
                },
                "summary": {
                    "total_return_pct": 8.2,
                    "sharpe_ratio": 1.35,
                    "max_drawdown_pct": 4.1,
                    "total_trades": 3,
                },
                "data_quality": {
                    "quality_tag": "incomplete",
                    "tags": ["missing_dates:1", "adjustment:forward"],
                },
            },
            "dataset_manifest_id": 7,
            "engine_version": "backtest-v2",
            "strategy_version": "8",
            "data_version": "dataset-hash",
            "fee_model_version": "v1",
            "slippage_bps": 8.0,
            "error_message": "",
        }

    def get_equity(self, run_id: int, *, owner_user_id: int | None, is_admin: bool):  # noqa: ANN001, ARG002
        return [
            {
                "trade_date": "2025-01-02",
                "cash": 100000.0,
                "market_value": 0.0,
                "equity": 100000.0,
                "daily_return_pct": 0.0,
                "drawdown_pct": 0.0,
                "exposure_pct": 0.0,
                "positions_count": 0,
                "benchmark_symbol": "000300",
                "benchmark_close": 4000.0,
                "benchmark_return_pct": 0.0,
                "payload": {},
            },
            {
                "trade_date": "2025-01-03",
                "cash": 70000.0,
                "market_value": 31200.0,
                "equity": 101200.0,
                "daily_return_pct": 1.2,
                "drawdown_pct": 0.0,
                "exposure_pct": 30.83,
                "positions_count": 1,
                "benchmark_symbol": "000300",
                "benchmark_close": 4012.0,
                "benchmark_return_pct": 0.3,
                "payload": {},
            },
        ]

    def get_trades(
        self,
        run_id: int,
        *,
        owner_user_id: int | None,
        is_admin: bool,
        limit=50,
        offset=0,
    ):  # noqa: ANN001, ARG002
        return {
            "run_id": run_id,
            "items": [
                {
                    "id": 1,
                    "run_id": run_id,
                    "order_id": 1,
                    "trade_date": "2025-01-03",
                    "symbol": "300001",
                    "name": "Test Tech",
                    "side": "buy",
                    "strategy_key": "first_board",
                    "signal_state": "buy_now",
                    "quantity": 1000,
                    "price": 10.2,
                    "gross_amount": 10200.0,
                    "fee_amount": 5.1,
                    "slippage_amount": 0.0,
                    "net_amount": -10205.1,
                    "pnl_amount": 0.0,
                    "pnl_pct": 0.0,
                    "holding_days": 0,
                    "entry_reason": "entry",
                    "exit_reason": "",
                    "market_state": "repair",
                    "sector_name": "software",
                    "payload": {},
                    "created_at": "2026-05-05T09:31:00+08:00",
                }
            ],
            "total": 1,
            "limit": limit,
            "offset": offset,
        }

    def cancel_run(self, run_id: int, *, owner_user_id: int | None, is_admin: bool):  # noqa: ANN001, ARG002
        self.cancelled_run_id = run_id
        return SimpleNamespace(id=run_id, status="cancelled", owner_user_id=owner_user_id)

    def get_monthly_returns(self, run_id: int, *, owner_user_id: int | None, is_admin: bool):  # noqa: ANN001, ARG002
        return {
            "run_id": run_id,
            "items": [
                {
                    "month": "2025-01",
                    "start_equity": 100000.0,
                    "end_equity": 103000.0,
                    "return_pct": 3.0,
                    "trading_days": 2,
                }
            ],
        }

    def get_attribution(self, run_id: int, *, owner_user_id: int | None, is_admin: bool):  # noqa: ANN001, ARG002
        return {
            "run_id": run_id,
            "strategy": [{"strategy_key": "first_board", "trade_count": 1, "net_pnl": 3000.0}],
            "industry": [{"bucket": "software", "trade_count": 1, "net_pnl": 3000.0}],
            "market_state": [{"bucket": "repair", "trade_count": 1, "win_rate_pct": 100.0}],
            "data_quality": [{"bucket": "ok", "trade_count": 1, "net_pnl": 3000.0}],
            "notes": ["行业分类可能存在历史偏差"],
        }

    def get_strategy_correlation(self, run_id: int, *, owner_user_id: int | None, is_admin: bool):  # noqa: ANN001, ARG002
        return {
            "run_id": run_id,
            "strategies": ["first_board", "volume_shrink"],
            "matrix": [
                {"strategy_key": "first_board", "correlations": {"first_board": 1.0, "volume_shrink": 0.25}},
                {"strategy_key": "volume_shrink", "correlations": {"first_board": 0.25, "volume_shrink": 1.0}},
            ],
        }

    def compare_runs(self, payload, *, owner_user_id: int | None, is_admin: bool):  # noqa: ANN001, ARG002
        return {
            "run_ids": payload.run_ids,
            "items": [
                {
                    "run_id": payload.run_ids[0],
                    "name": "first_board portfolio test",
                    "status": "succeeded",
                    "metrics": {"total_return_pct": 8.2, "sharpe_ratio": 1.35},
                }
            ],
            "equity_curves": [
                {"run_id": payload.run_ids[0], "points": [{"trade_date": "2025-01-02", "equity": 100000.0}]}
            ],
        }


@pytest.fixture()
def service_stub(monkeypatch: pytest.MonkeyPatch) -> _BacktestServiceStub:
    service = _BacktestServiceStub()
    if hasattr(backtests_route, "BacktestJobService"):
        monkeypatch.setattr(backtests_route, "BacktestJobService", lambda *args, **kwargs: service)
    elif hasattr(backtests_route, "backtest_service"):
        monkeypatch.setattr(backtests_route, "backtest_service", service)
    elif hasattr(backtests_route, "BacktestService"):
        monkeypatch.setattr(backtests_route, "BacktestService", lambda *args, **kwargs: service)
    else:
        pytest.fail("backtests route must expose an injectable backtest service for deterministic tests")
    return service


@pytest.fixture()
def client(service_stub: _BacktestServiceStub) -> TestClient:  # noqa: ARG001
    app = FastAPI()
    app.include_router(backtests_route.router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: object()
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=1,
        username="owner",
        roles="",
        is_active=True,
    )
    return TestClient(app)


def test_backtests_router_is_registered_in_main_api_router() -> None:
    from app.api.router import api_router

    paths = {route.path for route in api_router.routes}

    assert "/backtests" in paths
    assert "/backtests/{run_id}" in paths
    assert "/backtests/{run_id}/equity" in paths
    assert "/backtests/{run_id}/trades" in paths
    assert "/backtests/{run_id}/cancel" in paths


def test_submit_backtest_requires_authentication(service_stub: _BacktestServiceStub) -> None:
    app = FastAPI()
    app.include_router(backtests_route.router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: object()
    unauthenticated = TestClient(app)

    response = unauthenticated.post("/api/backtests", json=_submit_payload())

    assert response.status_code in {401, 403}
    assert service_stub.submitted_payload is None


def test_submit_backtest_accepts_documented_v2_payload_aliases(
    client: TestClient,
    service_stub: _BacktestServiceStub,
) -> None:
    response = client.post("/api/backtests", json=_submit_payload())

    assert response.status_code in {200, 202}
    body = response.json()
    assert body["id"] == 42
    assert body["status"] in {"pending", "queued"}
    assert service_stub.submitted_payload is not None
    assert service_stub.submitted_payload["strategy_keys"] == ["first_board", "volume_shrink"]
    assert service_stub.submitted_payload["initial_cash"] == 500000


def test_submit_backtest_returns_queued_async_run_with_current_schema(
    client: TestClient,
    service_stub: _BacktestServiceStub,
) -> None:
    response = client.post("/api/backtests", json=_submit_payload_current_schema())

    assert response.status_code in {200, 202}
    body = response.json()
    assert body["id"] == 42
    assert body["status"] == "queued"
    assert service_stub.submitted_payload is not None
    assert service_stub.submitted_payload["strategy_keys"] == ["first_board", "volume_shrink"]
    assert service_stub.submitted_payload["initial_cash"] == 500000
    assert service_stub.submitted_payload["params"]["execution_model"] == "open_price"
    assert service_stub.submitted_payload["params"]["risk_limits"]["max_positions"] == 8


def test_list_detail_equity_and_trades_expose_reproducible_outputs(client: TestClient) -> None:
    listed = client.get("/api/backtests?limit=10&offset=0")
    detail = client.get("/api/backtests/42")
    equity = client.get("/api/backtests/42/equity")
    trades = client.get("/api/backtests/42/trades?limit=20&offset=0")

    assert listed.status_code == 200
    assert listed.json()["items"][0]["status"] == "succeeded"

    assert detail.status_code == 200
    detail_body = detail.json()
    assert detail_body["result"]["summary"]["total_trades"] == 3
    assert detail_body["result"]["metrics"]["sortino_ratio"] == 1.91
    assert detail_body["result"]["metrics"]["calmar_ratio"] == 2.0
    assert detail_body["result"]["metrics"]["benchmark_alpha_pct"] == 3.1
    assert detail_body["result"]["metrics"]["information_ratio"] == 0.72
    assert detail_body["result"]["data_quality"]["quality_tag"] == "incomplete"
    assert "adjustment:forward" in detail_body["result"]["data_quality"]["tags"]
    assert detail_body["engine_version"]
    assert detail_body["strategy_version"]
    assert detail_body["data_version"]
    assert detail_body["fee_model_version"]

    assert equity.status_code == 200
    assert equity.json()["items"][0]["equity"] == 100000.0
    assert {"trade_date", "equity", "cash", "market_value", "drawdown_pct"} <= set(equity.json()["items"][0])

    assert trades.status_code == 200
    trade = trades.json()["items"][0]
    assert {"trade_date", "symbol", "side", "quantity", "price", "fee_amount", "net_amount"} <= set(trade)


def test_cancel_running_backtest_marks_run_cancelled(client: TestClient, service_stub: _BacktestServiceStub) -> None:
    response = client.post("/api/backtests/42/cancel")

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert service_stub.cancelled_run_id == 42


def test_analysis_endpoints_return_typed_shapes(client: TestClient) -> None:
    monthly = client.get("/api/backtests/42/monthly-returns")
    attribution = client.get("/api/backtests/42/attribution")
    correlation = client.get("/api/backtests/42/strategy-correlation")
    comparison = client.post("/api/backtests/compare", json={"run_ids": [42, 43]})

    assert monthly.status_code == 200
    assert monthly.json()["items"][0]["month"] == "2025-01"
    assert monthly.json()["items"][0]["return_pct"] == 3.0

    assert attribution.status_code == 200
    assert attribution.json()["strategy"][0]["strategy_key"] == "first_board"
    assert attribution.json()["industry"][0]["bucket"] == "software"

    assert correlation.status_code == 200
    assert correlation.json()["matrix"][0]["correlations"]["first_board"] == 1.0

    assert comparison.status_code == 200
    assert comparison.json()["run_ids"] == [42, 43]
    assert comparison.json()["items"][0]["metrics"]["sharpe_ratio"] == 1.35


def test_job_service_create_run_only_queues_without_starting_daemon_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ForbiddenThread:
        def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
            raise AssertionError("create_run must not start a web daemon thread")

    monkeypatch.setattr(threading, "Thread", ForbiddenThread)
    SessionLocal = _sqlite_session_factory()

    with SessionLocal() as db:
        detail = BacktestJobService(db).create_run(
            BacktestRunCreate(**_submit_payload_current_schema()),
            owner_user_id=7,
        )

        row = db.get(BacktestRun, detail.id)

    assert detail.status == "queued"
    assert detail.progress_pct == 0.0
    assert detail.started_at is None
    assert row is not None
    assert row.status == "queued"
    assert row.started_at is None
    assert row.finished_at is None


def test_backtest_worker_run_once_executes_queued_job(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.backtest_worker import BacktestWorker

    SessionLocal = _sqlite_session_factory()
    with SessionLocal() as db:
        created = BacktestJobService(db).create_run(
            BacktestRunCreate(**_submit_payload_current_schema()),
            owner_user_id=7,
        )

    def fake_run_engine(self, run: BacktestRun, cancel_token) -> BacktestResult:  # noqa: ANN001
        assert run.status == "running"
        assert not cancel_token.is_cancelled()
        return SimpleNamespace(status="succeeded")

    def fake_persist_result(self, run_id: int, result: BacktestResult) -> None:
        run = self.db.get(BacktestRun, run_id)
        assert run is not None
        run.status = result.status
        run.progress_pct = 100.0
        run.final_equity = 501000.0
        self.db.commit()

    monkeypatch.setattr(BacktestJobService, "_run_engine", fake_run_engine)
    monkeypatch.setattr(BacktestJobService, "_persist_result", fake_persist_result)

    outcome = BacktestWorker(session_factory=SessionLocal, max_duration_seconds=60).run_once()

    with SessionLocal() as db:
        row = db.execute(select(BacktestRun).where(BacktestRun.id == created.id)).scalar_one()

    assert outcome is not None
    assert outcome.run_id == created.id
    assert outcome.status == "succeeded"
    assert row.status == "succeeded"
    assert row.started_at is not None
    assert row.finished_at is not None
    assert row.progress_pct == 100.0


def test_backtest_worker_respects_process_semaphore(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import backtest_worker as worker_module
    from app.services.backtest_worker import BacktestWorker

    @contextmanager
    def denied_slot():
        yield False

    monkeypatch.setattr(worker_module, "backtest_execution_slot", denied_slot)
    SessionLocal = _sqlite_session_factory()
    with SessionLocal() as db:
        created = BacktestJobService(db).create_run(
            BacktestRunCreate(**_submit_payload_current_schema()),
            owner_user_id=7,
        )

    outcome = BacktestWorker(session_factory=SessionLocal, max_duration_seconds=60).run_once()

    with SessionLocal() as db:
        row = db.get(BacktestRun, created.id)

    assert outcome is None
    assert row is not None
    assert row.status == "queued"
    assert row.started_at is None


def test_persistence_does_not_overwrite_cancelled_run_with_succeeded_result() -> None:
    SessionLocal = _sqlite_session_factory()
    with SessionLocal() as db:
        created = BacktestJobService(db).create_run(
            BacktestRunCreate(**_submit_payload_current_schema()),
            owner_user_id=7,
        )
        row = db.get(BacktestRun, created.id)
        assert row is not None
        row.status = "cancelled"
        row.progress_pct = 12.0
        db.commit()

        BacktestResultPersistence(db).persist(row, _minimal_succeeded_result())
        db.refresh(row)

        assert row.status == "cancelled"
        assert row.progress_pct == 12.0
        assert row.final_equity == row.initial_cash
        assert row.result_json == "{}"


def test_persistence_links_realized_trade_to_matching_sell_order() -> None:
    SessionLocal = _sqlite_session_factory()
    with SessionLocal() as db:
        run = BacktestRun(
            name="order-link",
            status="running",
            initial_cash=100000.0,
            final_equity=100000.0,
            progress_pct=0.0,
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        BacktestResultPersistence(db).persist(run, _result_with_buy_sell_orders())
        persisted_trade = db.execute(select(BacktestTrade).where(BacktestTrade.run_id == run.id)).scalar_one()

    assert persisted_trade.order_id is not None
    assert persisted_trade.order_id != 1


def test_worker_marks_timed_out_run_with_timeout_status() -> None:
    from app.services.backtest_worker import BacktestWorker

    SessionLocal = _sqlite_session_factory()
    with SessionLocal() as db:
        created = BacktestJobService(db).create_run(
            BacktestRunCreate(**_submit_payload_current_schema()),
            owner_user_id=7,
        )
        row = db.get(BacktestRun, created.id)
        assert row is not None
        row.status = "running"
        row.started_at = row.created_at
        db.commit()

    outcome = BacktestWorker(session_factory=SessionLocal, max_duration_seconds=0.001).run_once()

    with SessionLocal() as db:
        row = db.get(BacktestRun, created.id)

    assert outcome is not None
    assert outcome.status == "timeout"
    assert row is not None
    assert row.status == "timeout"
    assert row.error_message == "回测执行超时"


def test_job_service_analysis_methods_return_basic_shapes() -> None:
    SessionLocal = _sqlite_session_factory()
    with SessionLocal() as db:
        created = BacktestJobService(db).create_run(
            BacktestRunCreate(**_submit_payload_current_schema()),
            owner_user_id=7,
        )
        row = db.get(BacktestRun, created.id)
        assert row is not None
        row.status = "succeeded"
        row.final_equity = 103000.0
        row.result_json = (
            '{"metrics":{"total_return_pct":3.0,"sharpe_ratio":1.2,'
            '"by_strategy":{"first_board":{"trade_count":1,"net_pnl":3000.0,"win_rate_pct":100.0,"avg_return_pct":3.0}}},'
            '"attribution":{"industry":[{"bucket":"software","trade_count":1,"net_pnl":3000.0}],'
            '"market_state":[{"bucket":"repair","trade_count":1,"win_rate_pct":100.0}],'
            '"data_quality":[{"bucket":"ok","trade_count":1}],"notes":["行业分类可能存在历史偏差"]}}'
        )
        db.add_all(
            [
                BacktestDailySnapshot(
                    run_id=row.id,
                    trade_date="2025-01-02",
                    equity=100000.0,
                    daily_return_pct=0.0,
                    drawdown_pct=0.0,
                ),
                BacktestDailySnapshot(
                    run_id=row.id,
                    trade_date="2025-01-31",
                    equity=103000.0,
                    daily_return_pct=3.0,
                    drawdown_pct=0.0,
                ),
                BacktestTrade(
                    run_id=row.id,
                    trade_date="2025-01-31",
                    symbol="300001",
                    side="sell",
                    strategy_key="first_board",
                    quantity=1000,
                    price=10.3,
                    pnl_amount=3000.0,
                    pnl_pct=3.0,
                    market_state="repair",
                    sector_name="software",
                ),
            ]
        )
        db.commit()

        service = BacktestJobService(db)
        monthly = service.get_monthly_returns(row.id, owner_user_id=7, is_admin=False)
        attribution = service.get_attribution(row.id, owner_user_id=7, is_admin=False)
        correlation = service.get_strategy_correlation(row.id, owner_user_id=7, is_admin=False)
        comparison = service.compare_runs(
            backtests_route.BacktestCompareRequest(run_ids=[row.id]),
            owner_user_id=7,
            is_admin=False,
        )

    assert monthly.items[0].month == "2025-01"
    assert monthly.items[0].return_pct == pytest.approx(3.0)
    assert attribution.strategy[0].strategy_key == "first_board"
    assert attribution.industry[0]["bucket"] == "software"
    assert correlation.matrix[0].correlations["first_board"] == 1.0
    assert comparison.items[0].metrics["sharpe_ratio"] == 1.2
    assert comparison.equity_curves[0].points[0].equity == 100000.0


def test_backtest_detail_enforces_owner_or_admin(client: TestClient) -> None:
    response = client.get("/api/backtests/403")

    assert response.status_code == 403


def _submit_payload() -> dict[str, Any]:
    return {
        "name": "first_board + volume_shrink portfolio test",
        "start_date": "2025-01-02",
        "end_date": "2026-04-30",
        "initial_capital": 500000,
        "strategies": ["first_board", "volume_shrink"],
        "param_overrides": {"first_board": {"min_score": 82}},
        "execution_model": "open_price",
        "slippage_model": "fixed",
        "risk_limits": {"max_position_pct": 0.30, "max_positions": 8},
        "benchmark": "000300",
    }


def _submit_payload_current_schema() -> dict[str, Any]:
    return {
        "name": "first_board + volume_shrink portfolio test",
        "start_date": "2025-01-02",
        "end_date": "2026-04-30",
        "initial_cash": 500000,
        "strategy_keys": ["first_board", "volume_shrink"],
        "params": {
            "param_overrides": {"first_board": {"min_score": 82}},
            "execution_model": "open_price",
            "risk_limits": {"max_position_pct": 0.30, "max_positions": 8},
        },
        "benchmark_symbol": "000300",
        "engine_version": "backtest-v2",
        "strategy_version": "8",
        "data_version": "dataset-hash",
        "fee_model_version": "v1",
    }


def _dump(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, dict):
        return value
    return dict(value)


def _minimal_succeeded_result() -> BacktestResult:
    return BacktestResult(
        version="backtest-core-v2.0",
        config={},
        data_quality=DataQualityReport(
            version="daily_bar_snapshots:v1",
            start_date="2025-01-02",
            end_date="2025-01-06",
            symbol_count=0,
            trade_date_count=0,
        ),
        metrics={"final_equity": 501000.0},
        equity_curve=[],
        orders=[],
        trades=[],
        status="succeeded",
    )


def _result_with_buy_sell_orders() -> BacktestResult:
    return BacktestResult(
        version="backtest-core-v2.0",
        config={},
        data_quality=DataQualityReport(
            version="daily_bar_snapshots:v1",
            start_date="2025-01-02",
            end_date="2025-01-06",
            symbol_count=1,
            trade_date_count=3,
        ),
        metrics={"final_equity": 101000.0},
        equity_curve=[],
        orders=[
            BacktestOrder(
                trade_date="2025-01-02",
                symbol="300001",
                side="buy",
                quantity=1000,
                status="filled",
                strategy_key="first_board",
                fill_price=10.0,
            ),
            BacktestOrder(
                trade_date="2025-01-06",
                symbol="300001",
                side="sell",
                quantity=1000,
                status="filled",
                strategy_key="first_board",
                fill_price=11.0,
                reason="take_profit",
            ),
        ],
        trades=[
            RealizedTrade(
                symbol="300001",
                name="测试股份",
                strategy_key="first_board",
                entry_date="2025-01-02",
                exit_date="2025-01-06",
                quantity=1000,
                entry_price=10.0,
                exit_price=11.0,
                gross_pnl=1000.0,
                net_pnl=990.0,
                return_pct=9.9,
                fee_amount=10.0,
                holding_days=2,
                exit_reason="take_profit",
            )
        ],
        status="succeeded",
    )


def _sqlite_session_factory():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
