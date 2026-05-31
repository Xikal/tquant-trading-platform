from __future__ import annotations

import json
from datetime import date, datetime
from types import SimpleNamespace

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.schema_defs.phase4 import RuntimeTaskCreate
from app.models.entities import ProductionSignalLedger, SignalRealizedOutcome, StrategyDriftSnapshot
from app.services.tasks import RuntimeTaskQueue
from app.services.tasks.registry import analytics_task_registry
from app.services.tasks import worker as worker_module
from app.services.low_buy.strategy_policy import participates_in_priority_board
from app.services.track_record.drift_metrics import compute_strategy_drift
from app.services.track_record.drift_alerts import maybe_send_drift_alert


def test_compute_strategy_drift_flags_decay_without_auto_policy_change() -> None:
    Session = _session_factory()
    with Session() as db:
        for index, return_pct in enumerate([-2.0, -1.5, -1.0, -0.5, 0.5], start=1):
            ledger = _ledger(index, expected_pf=2.0, expected_avg=2.0, expected_max5=4.0, expected_max10=5.0)
            db.add(ledger)
            db.flush()
            db.add(_outcome(ledger.id, horizon_days=5, return_pct=return_pct))
        before_policy = participates_in_priority_board("first_board")

        snapshot = compute_strategy_drift(db, "first_board", window_days=60, as_of=date(2026, 6, 30), min_sample=5)
        db.commit()
        stored = db.execute(select(StrategyDriftSnapshot)).scalar_one()

    assert before_policy is True
    assert participates_in_priority_board("first_board") is True
    assert snapshot.drift_flag == "decay_advisory"
    assert stored.drift_flag == "decay_advisory"
    assert stored.sample_settled == 5
    assert stored.realized_pf < stored.expected_pf
    assert stored.decay_pct < 0


def test_compute_strategy_drift_insufficient_sample_does_not_alert(monkeypatch) -> None:
    Session = _session_factory()
    sent: list[object] = []

    class Notifier:
        def supports_channel(self, channel: str = "feishu") -> bool:
            return True

        def send_test(self, payload):  # noqa: ANN001
            sent.append(payload)
            return SimpleNamespace(ok=True)

    monkeypatch.setattr("app.services.track_record.drift_alerts.AgentNotificationService", Notifier)
    with Session() as db:
        ledger = _ledger(1, expected_pf=2.0, expected_avg=2.0)
        db.add(ledger)
        db.flush()
        db.add(_outcome(ledger.id, horizon_days=5, return_pct=-3.0))
        snapshot = compute_strategy_drift(db, "first_board", window_days=60, as_of=date(2026, 6, 30), min_sample=5)
        alert = maybe_send_drift_alert(snapshot)

    assert snapshot.drift_flag == "insufficient_sample"
    assert alert == {"ok": True, "sent": False, "reason": "insufficient_sample"}
    assert sent == []


def test_drift_alert_is_flag_gated(monkeypatch) -> None:
    Session = _session_factory()
    sent: list[object] = []

    class Notifier:
        def supports_channel(self, channel: str = "feishu") -> bool:
            return True

        def send_test(self, payload):  # noqa: ANN001
            sent.append(payload)
            return SimpleNamespace(ok=True)

    monkeypatch.setattr("app.services.track_record.drift_alerts.AgentNotificationService", Notifier)
    with Session() as db:
        for index in range(5):
            ledger = _ledger(index + 1, expected_pf=2.0, expected_avg=2.0)
            db.add(ledger)
            db.flush()
            db.add(_outcome(ledger.id, horizon_days=5, return_pct=-2.0))
        snapshot = compute_strategy_drift(db, "first_board", window_days=60, as_of=date(2026, 6, 30), min_sample=5)
        alert = maybe_send_drift_alert(snapshot)

    assert snapshot.drift_flag == "decay_advisory"
    assert alert == {"ok": True, "sent": False, "reason": "DRIFT_ALERT_ENABLED=false"}
    assert sent == []


def test_analytics_worker_consumes_strategy_drift_refresh(monkeypatch) -> None:
    Session = _session_factory()
    calls: list[dict[str, object]] = []

    def fake_compute_all_strategy_drift(db, *, window_days, as_of, min_sample):  # noqa: ANN001
        calls.append({"db": db, "window_days": window_days, "as_of": as_of, "min_sample": min_sample})
        return [
            SimpleNamespace(
                strategy_key="first_board",
                drift_flag="ok",
                sample_settled=20,
                realized_pf=1.5,
                expected_pf=1.6,
                decay_pct=-5.0,
            )
        ]

    def fake_alert(snapshot):  # noqa: ANN001
        return {"ok": True, "sent": False, "reason": snapshot.drift_flag}

    monkeypatch.setattr("app.services.track_record.drift_metrics.compute_all_strategy_drift", fake_compute_all_strategy_drift)
    monkeypatch.setattr("app.services.track_record.drift_alerts.maybe_send_drift_alert", fake_alert)
    monkeypatch.setattr(worker_module, "SessionLocal", Session)
    with Session() as db:
        task = RuntimeTaskQueue(db).enqueue(
            RuntimeTaskCreate(
                task_type="strategy_drift_refresh",
                payload={"as_of_date": "2026-06-30", "window_days": 60, "min_sample": 5},
                priority=10,
            )
        )

    worker = worker_module.RuntimeTaskWorker(
        registry=analytics_task_registry(),
        worker_id="pytest-analytics",
        poll_interval_seconds=0.01,
    )
    assert worker.run_once() is True
    with Session() as db:
        stored = RuntimeTaskQueue(db).get(task.id)

    assert stored.status == "succeeded"
    assert stored.result["ok"] is True
    assert stored.result["task_type"] == "strategy_drift_refresh"
    assert stored.result["worker_scope"] == "analytics-worker"
    assert stored.result["snapshots"][0]["strategy_key"] == "first_board"
    assert calls[0]["window_days"] == 60
    assert calls[0]["as_of"] == date(2026, 6, 30)
    assert calls[0]["min_sample"] == 5


def _session_factory():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)


def _ledger(
    index: int,
    *,
    expected_pf: float,
    expected_avg: float,
    expected_max5: float = 4.0,
    expected_max10: float = 6.0,
) -> ProductionSignalLedger:
    return ProductionSignalLedger(
        signal_date=date(2026, 6, min(index, 28)),
        strategy_key="first_board",
        symbol=f"600{index:03d}",
        name=f"样本{index}",
        signal_state="buy_now" if index % 2 else "soft_buy_now",
        production_score=80.0,
        priority_score=90.0,
        expected_horizon_returns_json=json.dumps(
            {
                "avg_net_return_pct": expected_avg,
                "profit_factor": expected_pf,
                "sample_settled": 30,
                "5": expected_max5,
                "10": expected_max10,
            }
        ),
        signal_time=datetime(2026, 6, min(index, 28), 15, 1),
        data_cutoff_time=datetime(2026, 6, min(index, 28), 15, 0),
        return_start_time=datetime(2026, 6, min(index, 28), 9, 30),
    )


def _outcome(ledger_id: int, *, horizon_days: int, return_pct: float) -> SignalRealizedOutcome:
    return SignalRealizedOutcome(
        ledger_id=ledger_id,
        horizon_days=horizon_days,
        return_pct=return_pct,
        max_gain_pct=max(return_pct, 0.0),
        max_drawdown_pct=min(return_pct, 0.0),
        exit_reason=f"horizon_{horizon_days}d",
        return_start_time=datetime(2026, 6, 30, 9, 30),
        settled=True,
        data_quality="ok",
    )
