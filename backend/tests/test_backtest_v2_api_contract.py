from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.auth import get_current_user
from app.core.database import get_db

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
