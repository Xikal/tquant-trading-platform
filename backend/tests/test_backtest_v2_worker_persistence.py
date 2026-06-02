from __future__ import annotations

import threading
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

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
