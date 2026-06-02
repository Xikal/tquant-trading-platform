from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from app.runtime.background_jobs import _ml_incremental_train_due, shutdown_runtime_background_jobs, start_runtime_background_jobs


def test_ml_incremental_train_runs_after_friday_close() -> None:
    assert _ml_incremental_train_due(datetime(2026, 5, 15, 16, 0)) is True
    assert _ml_incremental_train_due(datetime(2026, 5, 15, 15, 59)) is False


def test_ml_incremental_train_does_not_run_on_monday() -> None:
    assert _ml_incremental_train_due(datetime(2026, 5, 11, 16, 30)) is False


def test_runtime_background_jobs_start_and_shutdown_strategy_evolution_scheduler(monkeypatch) -> None:
    calls: list[str] = []

    class _DummyThread:
        def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
            pass

        def start(self) -> None:
            calls.append("thread")

    monkeypatch.setattr("app.runtime.background_jobs._background_jobs_enabled", lambda: True)
    monkeypatch.setattr("app.runtime.background_jobs._acquire_background_leader_lock", lambda: True)
    monkeypatch.setattr("app.runtime.background_jobs.start_strategy_evolution_scheduler", lambda: calls.append("scheduler-start"))
    monkeypatch.setattr("app.runtime.background_jobs.shutdown_strategy_evolution_scheduler", lambda: calls.append("scheduler-stop"))
    monkeypatch.setattr("app.runtime.background_jobs.threading.Thread", _DummyThread)
    monkeypatch.setattr("app.runtime.background_jobs.task_manager.register_loop", lambda **kwargs: calls.append(kwargs["name"]))
    monkeypatch.setattr("app.runtime.background_jobs.task_manager.shutdown", lambda timeout=30: calls.append(f"shutdown:{timeout}"))
    monkeypatch.setattr("app.runtime.background_jobs.start_auto_trader", lambda config: calls.append("auto-trader-start"))
    monkeypatch.setattr("app.runtime.background_jobs.stop_auto_trader", lambda: calls.append("auto-trader-stop"))
    monkeypatch.setattr(
        "app.runtime.background_jobs.settings",
        SimpleNamespace(
            market_review_enabled=True,
            paper_perf_archive_enabled=False,
            strategy_validation_monthly_enabled=False,
            notification_signal_scan_enabled=False,
            paper_auto_trading_enabled=False,
            tquant_research_jobs_enabled=True,
            tquant_ml_jobs_enabled=True,
            tquant_factor_jobs_enabled=True,
            tquant_strategy_evolution_enabled=True,
        ),
    )

    start_runtime_background_jobs()
    shutdown_runtime_background_jobs(timeout=9)

    assert "scheduler-start" in calls
    assert "scheduler-stop" in calls
    assert "market_midday_review" in calls
    assert "market_close_review" in calls
    assert "paper_perf_archive" not in calls
    assert "ml_feature_drift_monitor_monthly" in calls
    assert "shutdown:9" in calls


def test_runtime_background_jobs_register_market_and_paper_loops_when_enabled(monkeypatch) -> None:
    calls: list[str] = []

    class _DummyThread:
        def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
            pass

        def start(self) -> None:
            calls.append("thread")

    monkeypatch.setattr("app.runtime.background_jobs._background_jobs_enabled", lambda: True)
    monkeypatch.setattr("app.runtime.background_jobs._acquire_background_leader_lock", lambda: True)
    monkeypatch.setattr("app.runtime.background_jobs.start_strategy_evolution_scheduler", lambda: calls.append("scheduler-start"))
    monkeypatch.setattr("app.runtime.background_jobs.shutdown_strategy_evolution_scheduler", lambda: calls.append("scheduler-stop"))
    monkeypatch.setattr("app.runtime.background_jobs.threading.Thread", _DummyThread)
    monkeypatch.setattr("app.runtime.background_jobs.task_manager.register_loop", lambda **kwargs: calls.append(kwargs["name"]))
    monkeypatch.setattr("app.runtime.background_jobs.task_manager.shutdown", lambda timeout=30: calls.append(f"shutdown:{timeout}"))
    monkeypatch.setattr("app.runtime.background_jobs.start_auto_trader", lambda config: calls.append("auto-trader-start"))
    monkeypatch.setattr("app.runtime.background_jobs.stop_auto_trader", lambda: calls.append("auto-trader-stop"))
    monkeypatch.setattr(
        "app.runtime.background_jobs.settings",
        SimpleNamespace(
            market_review_enabled=True,
            paper_perf_archive_enabled=True,
            paper_perf_ai_report_enabled=True,
            strategy_validation_monthly_enabled=True,
            notification_signal_scan_enabled=True,
            notification_signal_scan_interval_seconds=120,
            paper_auto_trading_enabled=False,
            database_url="mysql+pymysql://user:pass@localhost/db",
            tquant_research_jobs_enabled=True,
            tquant_ml_jobs_enabled=True,
            tquant_factor_jobs_enabled=True,
            tquant_strategy_evolution_enabled=True,
        ),
    )

    start_runtime_background_jobs()
    shutdown_runtime_background_jobs(timeout=7)

    assert "market_hourly_all_a_snapshot" in calls
    assert "market_midday_review" in calls
    assert "market_close_review" in calls
    assert "paper_perf_archive" in calls
    assert "scheduler-start" in calls
    assert "scheduler-stop" in calls
    assert "shutdown:7" in calls


def test_runtime_background_jobs_can_disable_market_reviews_independently(monkeypatch) -> None:
    calls: list[str] = []

    class _DummyThread:
        def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
            pass

        def start(self) -> None:
            calls.append("thread")

    monkeypatch.setattr("app.runtime.background_jobs._background_jobs_enabled", lambda: True)
    monkeypatch.setattr("app.runtime.background_jobs._acquire_background_leader_lock", lambda: True)
    monkeypatch.setattr("app.runtime.background_jobs.start_strategy_evolution_scheduler", lambda: calls.append("scheduler-start"))
    monkeypatch.setattr("app.runtime.background_jobs.shutdown_strategy_evolution_scheduler", lambda: calls.append("scheduler-stop"))
    monkeypatch.setattr("app.runtime.background_jobs.threading.Thread", _DummyThread)
    monkeypatch.setattr("app.runtime.background_jobs.task_manager.register_loop", lambda **kwargs: calls.append(kwargs["name"]))
    monkeypatch.setattr("app.runtime.background_jobs.task_manager.shutdown", lambda timeout=30: calls.append(f"shutdown:{timeout}"))
    monkeypatch.setattr("app.runtime.background_jobs.start_auto_trader", lambda config: calls.append("auto-trader-start"))
    monkeypatch.setattr("app.runtime.background_jobs.stop_auto_trader", lambda: calls.append("auto-trader-stop"))
    monkeypatch.setattr(
        "app.runtime.background_jobs.settings",
        SimpleNamespace(
            market_review_enabled=False,
            paper_perf_archive_enabled=True,
            paper_perf_ai_report_enabled=True,
            strategy_validation_monthly_enabled=False,
            notification_signal_scan_enabled=False,
            paper_auto_trading_enabled=False,
            database_url="mysql+pymysql://user:pass@localhost/db",
            tquant_research_jobs_enabled=True,
            tquant_ml_jobs_enabled=True,
            tquant_factor_jobs_enabled=True,
            tquant_strategy_evolution_enabled=True,
        ),
    )

    start_runtime_background_jobs()
    shutdown_runtime_background_jobs(timeout=7)

    assert "market_midday_review" not in calls
    assert "market_close_review" not in calls
    assert "paper_perf_archive" in calls


def test_runtime_background_jobs_keep_research_loops_off_by_default(monkeypatch) -> None:
    calls: list[str] = []

    class _DummyThread:
        def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
            pass

        def start(self) -> None:
            calls.append("thread")

    monkeypatch.setattr("app.runtime.background_jobs._background_jobs_enabled", lambda: True)
    monkeypatch.setattr("app.runtime.background_jobs._acquire_background_leader_lock", lambda: True)
    monkeypatch.setattr("app.runtime.background_jobs.start_strategy_evolution_scheduler", lambda: calls.append("scheduler-start"))
    monkeypatch.setattr("app.runtime.background_jobs.threading.Thread", _DummyThread)
    monkeypatch.setattr("app.runtime.background_jobs.task_manager.register_loop", lambda **kwargs: calls.append(kwargs["name"]))
    monkeypatch.setattr("app.runtime.background_jobs.start_auto_trader", lambda config: calls.append("auto-trader-start"))
    monkeypatch.setattr(
        "app.runtime.background_jobs.settings",
        SimpleNamespace(
            market_review_enabled=True,
            paper_perf_archive_enabled=True,
            paper_perf_ai_report_enabled=True,
            strategy_validation_monthly_enabled=True,
            notification_signal_scan_enabled=False,
            paper_auto_trading_enabled=False,
            database_url="mysql+pymysql://user:pass@localhost/db",
            tquant_research_jobs_enabled=False,
            tquant_ml_jobs_enabled=False,
            tquant_factor_jobs_enabled=False,
            tquant_strategy_evolution_enabled=False,
        ),
    )

    start_runtime_background_jobs()

    assert "scheduler-start" not in calls
    assert "strategy_validation_monthly" not in calls
    assert "backtest_research_worker" not in calls
    assert "low_buy_strategy_governance" not in calls
    assert "ml_signal_incremental_train_weekly" not in calls
    assert "ml_feature_drift_monitor_monthly" not in calls
    assert "factor_mining_monthly" not in calls


def test_web_role_does_not_register_runtime_background_loops(monkeypatch) -> None:
    calls: list[str] = []

    monkeypatch.setattr("app.runtime.background_jobs._background_jobs_enabled", lambda: True)
    monkeypatch.setattr("app.runtime.background_jobs._runtime_background_role", lambda: "web")
    monkeypatch.setattr("app.runtime.background_jobs._acquire_background_leader_lock", lambda: calls.append("lock") or True)
    monkeypatch.setattr("app.runtime.background_jobs.threading.Thread", lambda *args, **kwargs: calls.append("thread"))
    monkeypatch.setattr("app.runtime.background_jobs.task_manager.register_loop", lambda **kwargs: calls.append(kwargs["name"]))
    monkeypatch.setattr(
        "app.runtime.background_jobs.settings",
        SimpleNamespace(
            market_review_enabled=True,
            paper_perf_archive_enabled=True,
            paper_perf_ai_report_enabled=True,
            strategy_validation_monthly_enabled=True,
            notification_signal_scan_enabled=True,
            notification_signal_scan_interval_seconds=120,
            paper_auto_trading_enabled=True,
            database_url="mysql+pymysql://user:pass@localhost/db",
            tquant_research_jobs_enabled=True,
            tquant_ml_jobs_enabled=True,
            tquant_factor_jobs_enabled=True,
            tquant_strategy_evolution_enabled=True,
        ),
    )

    start_runtime_background_jobs()

    assert calls == []


def test_scheduler_role_registers_runtime_background_loops(monkeypatch) -> None:
    calls: list[str] = []

    class _DummyThread:
        def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
            pass

        def start(self) -> None:
            calls.append("thread")

    monkeypatch.setattr("app.runtime.background_jobs._background_jobs_enabled", lambda: True)
    monkeypatch.setattr("app.runtime.background_jobs._runtime_background_role", lambda: "scheduler")
    monkeypatch.setattr("app.runtime.background_jobs._acquire_background_leader_lock", lambda: True)
    monkeypatch.setattr("app.runtime.background_jobs.start_strategy_evolution_scheduler", lambda: calls.append("scheduler-start"))
    monkeypatch.setattr("app.runtime.background_jobs.threading.Thread", _DummyThread)
    monkeypatch.setattr("app.runtime.background_jobs.task_manager.register_loop", lambda **kwargs: calls.append(kwargs["name"]))
    monkeypatch.setattr("app.runtime.background_jobs.start_auto_trader", lambda config: calls.append("auto-trader-start"))
    monkeypatch.setattr(
        "app.runtime.background_jobs.settings",
        SimpleNamespace(
            market_review_enabled=False,
            paper_perf_archive_enabled=False,
            strategy_validation_monthly_enabled=False,
            notification_signal_scan_enabled=False,
            paper_auto_trading_enabled=False,
            database_url="mysql+pymysql://user:pass@localhost/db",
            tquant_research_jobs_enabled=False,
            tquant_ml_jobs_enabled=False,
            tquant_factor_jobs_enabled=False,
            tquant_strategy_evolution_enabled=False,
        ),
    )

    start_runtime_background_jobs()

    assert "market_quote_cache_refresh" in calls
    assert "daily_bar_refresh" in calls
