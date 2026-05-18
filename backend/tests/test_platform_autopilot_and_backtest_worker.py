from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.entities import BacktestOptimization, RuntimeTask
from app.services.platform_autopilot import PlatformAutopilotService, _research_stuck_count, _runtime_count
from app.workers.backtest_queue_worker import BacktestQueueWorker


def _session_factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def test_runtime_failed_count_only_uses_recent_terminal_failures() -> None:
    SessionLocal = _session_factory()
    now = datetime.utcnow()
    with SessionLocal() as db:
        db.add_all(
            [
                RuntimeTask(task_type="old", status="failed", finished_at=now - timedelta(days=3)),
                RuntimeTask(task_type="recent", status="failed", finished_at=now - timedelta(hours=2)),
            ]
        )
        db.commit()

        assert _runtime_count(db, "failed", since=now - timedelta(hours=24)) == 1


def test_research_stuck_count_uses_started_at_for_running_tasks() -> None:
    SessionLocal = _session_factory()
    now = datetime.utcnow()
    cutoff = now - timedelta(minutes=10)
    with SessionLocal() as db:
        db.add_all(
            [
                BacktestOptimization(status="queued", created_at=now - timedelta(minutes=20)),
                BacktestOptimization(
                    status="running",
                    created_at=now - timedelta(hours=1),
                    started_at=now - timedelta(minutes=2),
                ),
                BacktestOptimization(
                    status="running",
                    created_at=now - timedelta(hours=1),
                    updated_at=now - timedelta(minutes=20),
                ),
            ]
        )
        db.commit()

        assert _research_stuck_count(db, BacktestOptimization, cutoff) == 2


def test_latest_data_check_rolls_back_failed_session(monkeypatch) -> None:
    class DummySession:
        rolled_back = False

        def rollback(self) -> None:
            self.rolled_back = True

    def boom(_db):
        raise RuntimeError("db failed")

    dummy_db = DummySession()
    monkeypatch.setattr("app.services.platform_autopilot.latest_data_status", boom)
    issues = []
    actions = []

    PlatformAutopilotService(dummy_db)._check_latest_data(
        auto_repair=False,
        issues=issues,
        actions=actions,
    )

    assert dummy_db.rolled_back is True
    assert issues[0].code == "latest_data_check_failed"


@dataclass
class _NormalResult:
    run_id: int = 1
    status: str = "succeeded"
    message: str = ""


@dataclass
class _ResearchResult:
    task_id: int = 2
    task_kind: str = "optimization"
    status: str = "succeeded"
    message: str = ""


class _FakeWorker:
    def __init__(self, results):
        self.results = list(results)
        self.calls = 0

    def run_once(self):
        self.calls += 1
        if not self.results:
            return None
        return self.results.pop(0)


def test_backtest_queue_worker_rotates_between_normal_and_research_tasks() -> None:
    worker = BacktestQueueWorker()
    normal = _FakeWorker([_NormalResult(), _NormalResult()])
    research = _FakeWorker([_ResearchResult()])
    worker.backtest_worker = normal
    worker.research_worker = research

    assert worker.run_once() is True
    assert worker.run_once() is True
    assert worker.run_once() is True

    assert normal.calls == 2
    assert research.calls == 1
