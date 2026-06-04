from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.workers import runtime_worker
from app.workers.heavy_research_tasks import HEAVY_RESEARCH_TASK_TYPES, execute_heavy_research_task


def _db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return factory()


def test_runtime_worker_registers_b1_heavy_task_types() -> None:
    registered = set(runtime_worker.RUNTIME_WORKER_TASK_TYPES)

    assert set(HEAVY_RESEARCH_TASK_TYPES).issubset(registered)
    assert "ml_signal_incremental_train" in registered
    assert "factor_mining_evaluate" in registered


def test_heavy_research_task_empty_analysis_batch_is_blocked() -> None:
    db = _db()

    result = execute_heavy_research_task("analysis_batch", {"items": []}, db)

    assert result == {"ok": False, "status": "blocked", "reason": "analysis_batch requires items"}


def test_heavy_research_task_runs_low_buy_execution_backtest(monkeypatch) -> None:
    db = _db()
    calls = []

    class _Response:
        def model_dump(self, mode="python"):  # noqa: ARG002
            return {"ok": True, "status": "research_only", "sample_count": 3}

    class _Service:
        def execution_backtest(self, **kwargs):  # noqa: ANN001
            calls.append(kwargs)
            return _Response()

    monkeypatch.setattr("app.services.low_buy_screener.LowBuyScreenerService", lambda: _Service())

    result = execute_heavy_research_task(
        "low_buy_execution_backtest",
        {"strategy": "first_board", "lookback_days": 260, "limit": 1000},
        db,
    )

    assert result["status"] == "research_only"
    assert calls[0]["lookback_days"] == 260
    assert calls[0]["limit"] == 1000


def test_runtime_worker_dispatches_heavy_research_task(monkeypatch) -> None:
    db = _db()
    calls = []
    monkeypatch.setenv("TQUANT_RESEARCH_JOBS_ENABLED", "true")
    monkeypatch.setenv("TQUANT_ML_JOBS_ENABLED", "true")
    from app.core.config import get_settings

    get_settings.cache_clear()

    def _execute(task_type, payload, db_arg):  # noqa: ANN001
        calls.append((task_type, payload, db_arg))
        return {"ok": True, "task_type": task_type}

    monkeypatch.setattr(runtime_worker, "execute_heavy_research_task", _execute)

    try:
        result = runtime_worker._execute_task("ml_signal_build_samples", {"limit": 100}, db)
    finally:
        get_settings.cache_clear()

    assert result == {"ok": True, "task_type": "ml_signal_build_samples"}
    assert calls == [("ml_signal_build_samples", {"limit": 100}, db)]
