from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.backtest_entities import BacktestOptimization, BacktestValidation
from app.models.base import Base
from app.models.schema_defs.backtest import BacktestOptimizationCreate, BacktestValidationCreate
from app.services.backtest.data_provider import DailyBarDataProvider, DataQualityReport
from app.services.backtest.engine import BacktestConfig, BacktestResult
from app.services.backtest.optimizer import BacktestOptimizer, OptimizationCandidate
from app.services.backtest.validator import BacktestValidator
from app.services.backtest_optimization_service import BacktestOptimizationService
from app.services.backtest_research_worker import BacktestResearchWorker
from app.services.backtest_validation_service import BacktestValidationService

backtests_route = pytest.importorskip("app.api.routes.backtests")


def test_optimization_schema_rejects_non_allowlisted_params() -> None:
    with pytest.raises(ValueError):
        BacktestOptimizationCreate(**{**_optimization_payload(), "param_grid": {"lookback_days": [5, 10]}})


def test_validation_schema_accepts_walk_forward_payload() -> None:
    payload = BacktestValidationCreate(**_validation_payload())

    assert payload.strategy == "first_board"
    assert payload.window_count == 3
    assert set(payload.param_grid) == {"min_score", "max_holding_days"}


def test_optimization_endpoint_requires_admin_or_whitelist() -> None:
    client = _client_for_user(can_paper_trade=False, roles="")

    response = client.post("/api/backtests/optimize", json=_optimization_payload())

    assert response.status_code == 403


def test_validation_endpoint_requires_optimizer_access() -> None:
    client = _client_for_user(can_paper_trade=False, roles="")

    response = client.post("/api/backtests/validate", json=_validation_payload())

    assert response.status_code == 403


def test_validation_endpoint_accepts_optimizer_role() -> None:
    client = _client_for_user(can_paper_trade=False, roles="backtest_optimizer")

    response = client.post("/api/backtests/validate", json=_validation_payload())

    assert response.status_code == 200
    assert response.json()["status"] == "queued"
    assert response.json()["request"]["strategy_key"] == "first_board"


def test_cancel_optimization_marks_task_cancelled() -> None:
    SessionLocal = _sqlite_session_factory()
    with SessionLocal() as db:
        created = BacktestOptimizationService(db).create_task(
            BacktestOptimizationCreate(**_optimization_payload()),
            owner_user_id=7,
        )
        cancelled = BacktestOptimizationService(db).cancel_task(
            created.id,
            owner_user_id=7,
            is_admin=False,
        )

    assert cancelled.status == "cancelled"
    assert cancelled.cancelled_at is not None


def test_research_worker_executes_optimization_and_persists_candidate_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    SessionLocal = _sqlite_session_factory()
    with SessionLocal() as db:
        created = BacktestOptimizationService(db).create_task(
            BacktestOptimizationCreate(**_optimization_payload()),
            owner_user_id=7,
        )

    monkeypatch.setattr(
        "app.services.backtest.optimizer.BacktestEngine.run",
        _fake_engine_run,
    )
    monkeypatch.setattr(DailyBarDataProvider, "load_low_buy_signals", lambda self, **kwargs: [])
    monkeypatch.setattr(DailyBarDataProvider, "fetch_bars", lambda self, symbols, **kwargs: {})
    monkeypatch.setattr(DailyBarDataProvider, "fetch_trade_dates", lambda self, start_date, end_date: [])

    outcome = BacktestResearchWorker(session_factory=SessionLocal).run_once()

    with SessionLocal() as db:
        row = db.execute(select(BacktestOptimization).where(BacktestOptimization.id == created.id)).scalar_one()
        detail = BacktestOptimizationService(db).get_task(created.id, owner_user_id=7, is_admin=False)

    assert outcome is not None
    assert outcome.task_kind == "optimization"
    assert outcome.status == "succeeded"
    assert row.status == "succeeded"
    assert detail.result["auto_apply"] is False
    assert detail.result["candidates"][0]["params"]["min_score"] in {70, 80}
    assert {"params", "metrics", "score", "period", "rank"} <= set(detail.result["candidates"][0])
    assert {"best_is", "best_oos", "oos_downgrade"} <= set(detail.result)
    assert detail.result["validation_protocol"] == "mandatory_is_oos_split"
    assert detail.result["oos_required"] is True


def test_optimizer_surfaces_data_provider_failures() -> None:
    class _FailingProvider:
        def load_low_buy_signals(self, **kwargs):  # noqa: ANN003
            return []

        def fetch_trade_dates(self, start_date: str, end_date: str):  # noqa: ARG002
            raise RuntimeError("calendar unavailable")

    optimizer = BacktestOptimizer(SimpleNamespace(data_provider=_FailingProvider()))

    with pytest.raises(RuntimeError, match="回测优化无法读取交易日历"):
        optimizer.evaluate_param_sets(
            BacktestConfig(start_date="2025-01-02", end_date="2025-01-10", strategies=["first_board"]),
            param_sets=[{"min_score": 70}],
            start_date="2025-01-02",
            end_date="2025-01-10",
        )


def test_optimizer_requires_out_of_sample_window() -> None:
    optimizer = BacktestOptimizer(SimpleNamespace())

    with pytest.raises(ValueError, match="样本外验证"):
        optimizer.optimize_with_oos(
            BacktestConfig(start_date="2025-01-02", end_date="2025-01-20", strategies=["first_board"]),
            param_grid={"min_score": [70]},
            train_start="2025-01-02",
            train_end="2025-01-10",
            test_start="2025-01-10",
            test_end="2025-01-20",
        )


def test_walk_forward_counts_missing_oos_candidate_as_failed_window(monkeypatch: pytest.MonkeyPatch) -> None:
    train_candidate = OptimizationCandidate(
        params={"min_score": 80},
        score=1.2,
        metrics={
            "sharpe_ratio": 1.2,
            "total_return_pct": 8.0,
            "market_state_attribution": [{"market_state": "repair", "signal_count": 3}],
        },
        period="is",
        rank=1,
    )

    def fake_evaluate(self, base_config, *, period, **kwargs):  # noqa: ANN001, ARG001
        return [train_candidate] if period == "is" else []

    monkeypatch.setattr(BacktestOptimizer, "evaluate_param_sets", fake_evaluate)

    report = BacktestValidator(SimpleNamespace()).walk_forward_windows(
        BacktestConfig(start_date="2025-01-02", end_date="2025-01-20", strategies=["first_board"]),
        param_grid={"min_score": [80]},
        windows=[("2025-01-02", "2025-01-10", "2025-01-13", "2025-01-20")],
    )

    assert report.window_count == 1
    assert report.oos_pass_rate == 0
    assert report.windows[0].oos_failed is True
    assert report.windows[0].passed is False
    assert report.windows[0].overfit_signal is True
    assert report.windows[0].train_market_state_segments == [{"market_state": "repair", "signal_count": 3}]


def test_research_worker_executes_validation_and_persists_walk_forward_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    SessionLocal = _sqlite_session_factory()
    with SessionLocal() as db:
        created = BacktestValidationService(db).create_task(
            BacktestValidationCreate(**_validation_payload()),
            owner_user_id=7,
        )

    monkeypatch.setattr(
        "app.services.backtest.optimizer.BacktestEngine.run",
        _fake_engine_run,
    )
    monkeypatch.setattr(
        "app.services.backtest.validator.BacktestEngine.run",
        _fake_engine_run,
    )
    monkeypatch.setattr(DailyBarDataProvider, "load_low_buy_signals", lambda self, **kwargs: [])
    monkeypatch.setattr(DailyBarDataProvider, "fetch_bars", lambda self, symbols, **kwargs: {})
    monkeypatch.setattr(
        DailyBarDataProvider,
        "fetch_trade_dates",
        lambda self, start_date, end_date: [
            "2025-01-02",
            "2025-01-03",
            "2025-01-06",
            "2025-01-07",
            "2025-01-08",
            "2025-01-09",
            "2025-01-10",
            "2025-01-13",
            "2025-01-14",
            "2025-01-15",
            "2025-01-16",
            "2025-01-17",
        ],
    )

    outcome = BacktestResearchWorker(session_factory=SessionLocal).run_once()

    with SessionLocal() as db:
        row = db.execute(select(BacktestValidation).where(BacktestValidation.id == created.id)).scalar_one()
        detail = BacktestValidationService(db).get_task(created.id, owner_user_id=7, is_admin=False)

    assert outcome is not None
    assert outcome.task_kind == "validation"
    assert outcome.status == "succeeded"
    assert row.status == "succeeded"
    assert {"avg_oos_sharpe", "oos_pass_rate", "pbo_risk", "downgrade_review", "stability_conclusion"} <= set(
        detail.result
    )
    assert detail.result["windows"][0]["best_params"]
    assert "train_market_state_segments" in detail.result["windows"][0]


def _fake_engine_run(self, config, *, cancel_token=None):  # noqa: ANN001, ARG001
    min_score = 0
    if config.signals:
        min_score = int(config.signals[0].metadata.get("min_score", 0) or 0)
    total_return_pct = 8.0 + (float(config.max_position_pct or 0.0) * 10) + (min_score / 100)
    return BacktestResult(
        version="backtest-core-v2.0",
        config={},
        data_quality=DataQualityReport(
            version="daily_bar_snapshots:v1",
            start_date=config.start_date,
            end_date=config.end_date,
            symbol_count=0,
            trade_date_count=0,
        ),
        metrics={
            "total_return_pct": total_return_pct,
            "win_rate_pct": 55.0,
            "max_drawdown_pct": -3.0,
            "profit_factor": 1.4,
            "sharpe_ratio": 1.0 + float(config.max_position_pct or 0.0),
            "trade_count": 2,
            "market_state_attribution": [{"market_state": "repair", "signal_count": 2}],
        },
        equity_curve=[],
        orders=[],
        trades=[],
        status="succeeded",
    )


def _client_for_user(*, can_paper_trade: bool, roles: str) -> TestClient:
    SessionLocal = _sqlite_session_factory()
    app = FastAPI()
    app.include_router(backtests_route.router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: next(_db_override(SessionLocal))
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=7,
        username="tester",
        roles=roles,
        can_paper_trade=can_paper_trade,
        is_active=True,
    )
    return TestClient(app)


def _db_override(SessionLocal):
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _optimization_payload() -> dict[str, Any]:
    return {
        "name": "first_board 参数优化",
        "strategy": "first_board",
        "param_grid": {
            "min_score": [70, 80],
            "max_position_pct": [0.1, 0.2],
        },
        "train_start": "2025-01-02",
        "train_end": "2025-01-10",
        "test_start": "2025-01-13",
        "test_end": "2025-01-20",
        "optimization_target": "sharpe",
        "initial_capital": 500000,
        "execution_model": "open_price",
    }


def _validation_payload() -> dict[str, Any]:
    return {
        "name": "first_board Walk-forward",
        "strategy": "first_board",
        "param_grid": {
            "min_score": [70, 80],
            "max_holding_days": [3, 5],
        },
        "start_date": "2025-01-02",
        "end_date": "2025-01-31",
        "window_count": 3,
        "train_ratio": 0.67,
        "optimization_target": "sharpe",
        "initial_capital": 500000,
        "execution_model": "open_price",
    }


def _sqlite_session_factory():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
