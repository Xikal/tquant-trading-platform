from __future__ import annotations

import time
import warnings

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.entities import MLSignalSample
from app.models.schema_defs.market import IntradayMarketPulse
from app.workers import runtime_worker


def _db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return session_factory()


def test_runtime_worker_executes_monitor_snapshot_refresh(monkeypatch):
    db = _db()
    calls = []

    def _build_stub(db_arg, *, user_id: int, priority_limit: int):  # noqa: ANN001
        calls.append((db_arg, user_id, priority_limit))
        return {"ok": True, "user_id": user_id, "priority_limit": priority_limit}

    monkeypatch.setattr(runtime_worker, "build_and_store_monitor_snapshot", _build_stub)

    result = runtime_worker._execute_task(
        "monitor_snapshot_refresh",
        {"user_id": 3, "priority_limit": 99},
        db,
    )

    assert result == {"ok": True, "user_id": 3, "priority_limit": 30}
    assert calls == [(db, 3, 30)]


def test_runtime_worker_executes_market_pulse_refresh(monkeypatch):
    db = _db()
    calls = []

    def _refresh_stub(db_arg):  # noqa: ANN001
        calls.append(db_arg)
        return IntradayMarketPulse(
            updated_at="2026-05-31 10:30:00",
            data_quality="fresh",
            pulse_level="repair",
            pulse_text="worker refreshed",
        )

    recorded = []
    monkeypatch.setattr("app.api.routes.market.refresh_market_pulse_snapshot", _refresh_stub)
    monkeypatch.setattr(
        "app.services.market.pulse_history.record_market_pulse_event",
        lambda db_arg, pulse: recorded.append((db_arg, pulse.pulse_level)),
    )

    result = runtime_worker._execute_task(
        "market_pulse_refresh",
        {"reason": "test"},
        db,
    )

    assert result == {"ok": True, "data_quality": "fresh", "pulse_level": "repair"}
    assert calls == [db]
    assert recorded == [(db, "repair")]


def test_runtime_worker_executes_latest_data_watchdog(monkeypatch):
    db = _db()
    calls = []

    class _Watchdog:
        def run(self, db_arg, *, trade_date=None, notify=True, force_notify=False):  # noqa: ANN001
            calls.append((db_arg, trade_date, notify, force_notify))
            return {"ok": False, "status": "alert_sent", "expected_trade_date": trade_date}

    monkeypatch.setattr("app.services.latest_data_watchdog.LatestDailyBarWatchdog", lambda: _Watchdog())

    result = runtime_worker._execute_task(
        "latest_data_watchdog",
        {"expected_trade_date": "2026-06-03", "notify": True, "force_notify": True},
        db,
    )

    assert result == {"ok": False, "status": "alert_sent", "expected_trade_date": "2026-06-03"}
    assert calls == [(db, "2026-06-03", True, True)]


def test_runtime_worker_passes_expected_trade_date_to_daily_bar_refresh(monkeypatch):
    db = _db()
    calls = []

    class _RefreshService:
        def __init__(self, db_arg):  # noqa: ANN001
            calls.append(("init", db_arg))

        def refresh_latest(self, *, limit: int, expected_trade_date=None):  # noqa: ANN001
            calls.append(("refresh", limit, expected_trade_date))
            return {"ok": True, "expected_trade_date": expected_trade_date, "limit": limit}

    monkeypatch.setattr("app.services.daily_bar_refresh.DailyBarRefreshService", _RefreshService)

    result = runtime_worker._execute_task(
        "daily_bar_refresh",
        {"limit": 6000, "expected_trade_date": "2026-06-03"},
        db,
    )

    assert result["expected_trade_date"] == "2026-06-03"
    assert calls == [("init", db), ("refresh", 6000, "2026-06-03")]


def test_runtime_worker_chains_close_refresh_after_daily_bar_success(monkeypatch):
    db = _db()
    calls = []

    class _RefreshService:
        def __init__(self, _db_arg):  # noqa: ANN001
            pass

        def refresh_latest(self, **_kwargs):  # noqa: ANN003
            return {"ok": True, "trade_date": "2026-06-03", "daily_bar_count": 4950}

    monkeypatch.setattr("app.services.daily_bar_refresh.DailyBarRefreshService", _RefreshService)
    monkeypatch.setattr(
        "app.services.latest_data_close_refresh.enqueue_latest_data_close_refresh",
        lambda db_arg: calls.append(db_arg) or {"ok": True, "action": "publish_latest_trade_date"},
    )

    result = runtime_worker._execute_task("daily_bar_refresh", {"expected_trade_date": "2026-06-03"}, db)

    assert result["next_refresh_check"]["action"] == "publish_latest_trade_date"
    assert calls == [db]


def test_runtime_worker_keeps_heartbeat_fresh_during_long_task(monkeypatch):
    db = _db()
    heartbeats = []

    class _SessionFactory:
        def __call__(self):
            return db

    class _Queue:
        def __init__(self, _db_arg):  # noqa: ANN001
            pass

        def claim_next(self, *, worker_id, task_types=None):  # noqa: ANN001
            return type("Task", (), {"id": 7, "task_type": "noop", "payload_json": "{}"})()

        def mark_succeeded(self, task_id, result):  # noqa: ANN001
            assert task_id == 7
            assert result == {"ok": True}

    def _execute_task(_task_type, _payload, _db_arg):  # noqa: ANN001
        time.sleep(0.05)
        return {"ok": True}

    monkeypatch.setattr(runtime_worker, "SessionLocal", _SessionFactory())
    monkeypatch.setattr(runtime_worker, "RuntimeTaskQueue", _Queue)
    monkeypatch.setattr(runtime_worker, "_execute_task", _execute_task)
    monkeypatch.setattr(runtime_worker, "_record_worker_heartbeat", lambda _db_arg, *, worker_id: heartbeats.append(worker_id))
    monkeypatch.setattr(runtime_worker, "LONG_TASK_HEARTBEAT_SECONDS", 0.01)

    did_work = runtime_worker.RuntimeWorker(worker_id="runtime-test").run_once()

    assert did_work is True
    assert len(heartbeats) >= 3


def test_runtime_worker_executes_ml_incremental_train_task(tmp_path, monkeypatch):
    db = _db()
    monkeypatch.setenv("ML_SIGNAL_MODEL_DIR", str(tmp_path))
    monkeypatch.setenv("TQUANT_RESEARCH_JOBS_ENABLED", "true")
    monkeypatch.setenv("TQUANT_ML_JOBS_ENABLED", "true")
    from app.core.config import get_settings

    get_settings.cache_clear()
    for index in range(120):
        db.add(
            MLSignalSample(
                sample_key=f"paper-close:{index}",
                symbol="600000",
                trade_date="2026-05-08",
                strategy_key="first_board",
                source="paper",
                feature_json=(
                    '{"price": %s, "quantity": 100, "gross_amount": %s, '
                    '"strategy_known": 1, "market_state_known": 1, "is_sell": 1, '
                    '"priority_score": %s, "risk_score": %s, "volume_shrink_ratio": 0.7}'
                    % (10 + index / 10, 1000 + index, 70 + index % 8, index % 5)
                ),
                label_json='{"return_pct": 1.2}' if index % 2 == 0 else '{"return_pct": -0.8}',
            )
        )
    db.commit()

    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always", RuntimeWarning)
        result = runtime_worker._execute_task(
            "ml_signal_incremental_train",
            {"model_type": "logistic", "limit": 120, "min_samples": 100, "promote": False},
            db,
        )
    assert captured == []

    assert result["status"] in {"research", "failed"}
    assert result["sample_count"] >= 120
    get_settings.cache_clear()


def test_runtime_worker_blocks_research_task_when_disabled(monkeypatch):
    db = _db()
    monkeypatch.setenv("TQUANT_RESEARCH_JOBS_ENABLED", "false")
    monkeypatch.setenv("TQUANT_ML_JOBS_ENABLED", "false")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        try:
            runtime_worker._execute_task("ml_signal_incremental_train", {}, db)
        except RuntimeError as exc:
            assert "TQUANT_RESEARCH_JOBS_ENABLED" in str(exc)
        else:  # pragma: no cover
            raise AssertionError("expected disabled research task")
    finally:
        get_settings.cache_clear()


def test_runtime_worker_executes_batch_a_decision_context_tasks():
    db = _db()

    market_result = runtime_worker._execute_task("market_state_gate_refresh", {}, db)
    hard_risk_result = runtime_worker._execute_task("hard_risk_context_refresh", {}, db)

    assert market_result["ok"] is True
    assert market_result["worker_scope"] == "runtime-worker"
    assert market_result["gate"]["decision"] in {"allow", "reduce", "block", "wait", "research_only", "no_data"}
    assert hard_risk_result == {
        "ok": True,
        "worker_scope": "runtime-worker",
        "message": "hard risk context refresh uses synchronous signal snapshots in Batch A",
    }


def test_runtime_worker_executes_batch_b_decision_context_tasks(monkeypatch):
    db = _db()

    class _MarketData:
        def sector_relative_strength_rank(self, db_arg, *, limit: int, per_sector_limit: int):  # noqa: ANN001
            from app.models.schema_defs.market import SectorRelativeStrengthResponse

            assert db_arg is db
            assert limit == 6
            assert per_sector_limit == 4
            return SectorRelativeStrengthResponse(updated_at="2026-05-30T09:30:00+08:00", items=[])

    class _PaperPerformanceService:
        def __init__(self, db_arg):  # noqa: ANN001
            assert db_arg is db

        def compute_portfolio_execution_preview(self, account_id: int):
            return {"account_id": account_id, "max_5": {"portfolio_return_pct": 1.23}, "max_10": {"portfolio_return_pct": 2.34}}

    monkeypatch.setattr("app.services.market_data.MarketDataService", lambda: _MarketData())
    monkeypatch.setattr("app.services.paper.performance.PaperPerformanceService", _PaperPerformanceService)

    sector_result = runtime_worker._execute_task(
        "sector_leader_snapshot_refresh",
        {"limit": 6, "per_sector_limit": 4},
        db,
    )
    portfolio_result = runtime_worker._execute_task("paper_portfolio_execution_preview", {"account_id": 7}, db)
    promotion_result = runtime_worker._execute_task(
        "strategy_promotion_review",
        {
            "strategy_key": "n_pattern_long_wash",
            "review_date": "2026-05-30",
            "sample_count": 250,
            "profit_factor": 1.1,
            "average_trade_pct": 0.2,
            "max_drawdown_pct": -8.0,
            "max5_return_pct": 1.0,
            "max10_return_pct": 1.0,
            "quarterly_stability": 0.4,
            "walk_forward_pass": False,
            "oos_pass": False,
        },
        db,
    )

    assert sector_result["ok"] is True
    assert sector_result["worker_scope"] == "runtime-worker"
    assert sector_result["task_type"] == "sector_leader_snapshot_refresh"
    assert sector_result["item_count"] == 0
    assert portfolio_result["ok"] is True
    assert portfolio_result["preview"]["max_5"]["portfolio_return_pct"] == 1.23
    assert promotion_result["ok"] is True
    assert promotion_result["review"]["can_apply_override"] is False
    assert promotion_result["review"]["recommendation"] == "stay_research"


def test_runtime_worker_executes_signal_attribution_refresh(monkeypatch):
    db = _db()
    calls = []

    def _refresh_stub(db_arg, *, as_of_date, horizons, limit):  # noqa: ANN001
        calls.append((db_arg, as_of_date.isoformat(), horizons, limit))
        return {"ok": True, "status": "no_data", "worker_scope": "runtime-worker"}

    monkeypatch.setattr("app.services.decision_context.signal_attribution.refresh_signal_attributions", _refresh_stub)

    result = runtime_worker._execute_task(
        "signal_attribution_refresh",
        {"as_of_date": "2026-05-31", "horizons": [1, 3], "limit": 25},
        db,
    )

    assert result == {"ok": True, "status": "no_data", "worker_scope": "runtime-worker"}
    assert calls == [(db, "2026-05-31", [1, 3], 25)]


def test_runtime_worker_executes_intraday_entry_snapshot_refresh(monkeypatch):
    db = _db()
    calls = []

    def _refresh_stub(db_arg, *, symbols, trade_date, entry_context, bar_period, limit):  # noqa: ANN001
        calls.append((db_arg, symbols, trade_date.isoformat(), entry_context, bar_period, limit))
        return {"ok": True, "status": "no_data", "worker_scope": "runtime-worker"}

    monkeypatch.setattr("app.services.decision_context.intraday_entry.refresh_intraday_entry_snapshots", _refresh_stub)

    result = runtime_worker._execute_task(
        "intraday_entry_snapshot_refresh",
        {
            "symbols": ["600000"],
            "trade_date": "2026-05-31",
            "entry_context": {"600000": {"entry_zone_low": 9.6, "entry_zone_high": 10.0}},
            "bar_period": "1m",
            "limit": 80,
        },
        db,
    )

    assert result == {"ok": True, "status": "no_data", "worker_scope": "runtime-worker"}
    assert calls == [(db, ["600000"], "2026-05-31", {"600000": {"entry_zone_low": 9.6, "entry_zone_high": 10.0}}, "1m", 80)]


def test_runtime_worker_executes_event_risk_refresh(monkeypatch):
    db = _db()
    calls = []

    def _refresh_stub(db_arg, *, symbols, trade_date, limit_per_symbol):  # noqa: ANN001
        calls.append((db_arg, symbols, trade_date.isoformat(), limit_per_symbol))
        return {
            "ok": True,
            "status": "no_data",
            "worker_scope": "runtime-worker",
            "gate_owner": "production-traceability-no-research-gate",
        }

    monkeypatch.setattr("app.services.decision_context.event_risk.refresh_event_risk", _refresh_stub)

    result = runtime_worker._execute_task(
        "event_risk_refresh",
        {"symbols": ["600000"], "trade_date": "2026-05-31", "limit_per_symbol": 6},
        db,
    )

    assert result["ok"] is True
    assert result["worker_scope"] == "runtime-worker"
    assert result["gate_owner"] == "production-traceability-no-research-gate"
    assert calls == [(db, ["600000"], "2026-05-31", 6)]
