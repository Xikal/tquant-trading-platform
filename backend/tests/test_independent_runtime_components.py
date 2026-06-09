from __future__ import annotations

import subprocess
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.schema_defs.phase4 import RuntimeTaskCreate
from app.services.tasks import RuntimeTaskQueue
from app.services.tasks.registry import analytics_task_registry
from app.workers.runtime_worker import RUNTIME_WORKER_TASK_TYPES


ROOT_DIR = Path(__file__).resolve().parents[2]


def read_repo_file(relative_path: str) -> str:
    return (ROOT_DIR / relative_path).read_text(encoding="utf-8")


def print_command(component: str) -> str:
    result = subprocess.run(
        ["bash", str(ROOT_DIR / "scripts/run_platform_component.sh"), component, "--print-command"],
        cwd=ROOT_DIR,
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()


def _db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return session_factory()


def test_platform_components_print_independent_entrypoints() -> None:
    commands = {component: print_command(component) for component in (
        "web",
        "runtime-worker",
        "scheduler",
        "analytics-worker",
        "backtest-worker",
    )}

    assert "uvicorn app.main:app" in commands["web"]
    assert "RUNTIME_BACKGROUND_JOBS_ENABLED=${RUNTIME_BACKGROUND_JOBS_ENABLED:-false}" in commands["web"]
    assert "python -m app.workers.runtime_worker" in commands["runtime-worker"]
    assert "python -m app.workers.runtime_scheduler" in commands["scheduler"]
    assert "RUNTIME_BACKGROUND_ROLE=${RUNTIME_BACKGROUND_ROLE:-scheduler}" in commands["scheduler"]
    assert "RUNTIME_BACKGROUND_JOBS_ENABLED=${RUNTIME_BACKGROUND_JOBS_ENABLED:-true}" in commands["scheduler"]
    assert "backend/scripts/analytics_worker.py" in commands["analytics-worker"]
    assert "scripts/backtest_worker.py" in commands["backtest-worker"]


def test_mysql_compose_keeps_web_light_and_workers_independent() -> None:
    compose = read_repo_file("docker-compose.mysql.yml")

    assert "container_name: tquant-app-mysql" in compose
    assert "RUNTIME_BACKGROUND_ROLE: web" in compose
    assert "RUNTIME_BACKGROUND_JOBS_ENABLED: ${WEB_RUNTIME_BACKGROUND_JOBS_ENABLED:-false}" in compose
    assert "container_name: tquant-runtime-worker-mysql" in compose
    assert 'command: ["python", "-m", "app.workers.runtime_worker"]' in compose
    assert "RUNTIME_BACKGROUND_ROLE: worker" in compose
    assert "RUNTIME_WORKER_EMBED_SCHEDULER: ${RUNTIME_WORKER_EMBED_SCHEDULER:-false}" in compose
    assert "RUNTIME_SCHEDULER_LEADER_LOCK_TTL_SECONDS: ${RUNTIME_SCHEDULER_LEADER_LOCK_TTL_SECONDS:-60}" in compose
    assert "container_name: tquant-runtime-scheduler-mysql" in compose
    assert 'command: ["python", "-m", "app.workers.runtime_scheduler"]' in compose
    assert "RUNTIME_BACKGROUND_ROLE: scheduler" in compose
    assert "RUNTIME_BACKGROUND_JOBS_ENABLED: ${RUNTIME_SCHEDULER_BACKGROUND_JOBS_ENABLED:-true}" in compose
    assert "container_name: tquant-backtest-worker-mysql" in compose
    assert 'profiles: ["backtest"]' in compose
    assert 'command: ["python", "-m", "app.workers.backtest_queue_worker"]' in compose
    assert "container_name: tquant-analytics-worker-mysql" in compose
    assert 'command: ["python", "/app/backend/scripts/analytics_worker.py"' in compose
    assert "INSTALL_ANALYTICS: \"1\"" in compose


def test_runtime_analytics_and_backtest_claim_scopes_are_bounded() -> None:
    runtime_worker = read_repo_file("backend/app/workers/runtime_worker.py")
    heavy_research_tasks = read_repo_file("backend/app/workers/heavy_research_tasks.py")
    analytics_worker = read_repo_file("backend/scripts/analytics_worker.py")
    analytics_registry = read_repo_file("backend/app/services/tasks/registry.py")
    analytics_handlers = read_repo_file("backend/app/services/tasks/analytics_handlers.py")
    backtest_worker = read_repo_file("backend/app/workers/backtest_queue_worker.py")

    assert "RUNTIME_WORKER_TASK_TYPES" in runtime_worker
    assert "*HEAVY_RESEARCH_TASK_TYPES" in runtime_worker
    assert '"low_buy_execution_backtest"' in heavy_research_tasks
    assert '"analysis_batch"' in heavy_research_tasks
    assert '"paper_smart_t_backtest"' in heavy_research_tasks
    assert "queue.claim_next(worker_id=self.worker_id, task_types=RUNTIME_WORKER_TASK_TYPES)" in runtime_worker
    assert "analytics_task_registry()" in analytics_worker
    assert "RuntimeTaskWorker" in analytics_worker
    assert "register_analytics_handlers" in analytics_registry
    for task_type in (
        "analytics_export_daily_bars",
        "analytics_quality_check",
        "strategy_24m_duckdb_report",
        "data_quality_sla_refresh",
        "data_repair_run",
    ):
        assert task_type in analytics_handlers
    assert "BacktestWorker" in backtest_worker
    assert "BacktestResearchWorker" in backtest_worker
    assert "run_once" in backtest_worker


def test_runtime_and_analytics_workers_claim_only_their_task_types(monkeypatch) -> None:
    db = _db()
    monkeypatch.setattr("app.services.tasks.queue.publish_runtime_task_event", lambda event: None)
    queue = RuntimeTaskQueue(db)
    analytics = queue.enqueue(RuntimeTaskCreate(task_type="analytics_quality_check", payload={}, max_attempts=1))
    runtime = queue.enqueue(RuntimeTaskCreate(task_type="noop", payload={}, max_attempts=1))

    claimed_runtime = queue.claim_next(worker_id="runtime-worker", task_types=RUNTIME_WORKER_TASK_TYPES)
    claimed_analytics = queue.claim_next(worker_id="analytics-worker", task_types=analytics_task_registry().task_types())

    assert claimed_runtime is not None
    assert claimed_runtime.id == runtime.id
    assert claimed_runtime.task_type == "noop"
    assert claimed_analytics is not None
    assert claimed_analytics.id == analytics.id
    assert claimed_analytics.task_type == "analytics_quality_check"


def test_deploy_and_quick_verify_wait_for_independent_workers() -> None:
    deploy_script = read_repo_file("scripts/deploy_cloud_server.sh")
    quick_script = read_repo_file("scripts/quick_cloud_deploy.sh")

    for script in (deploy_script, quick_script):
        assert "tquant-app-mysql" in script
        assert "tquant-runtime-scheduler-mysql" in script
        assert "tquant-runtime-worker-mysql" in script
        assert "DEPLOY_WITH_BACKTEST_WORKER" in script
        assert "backtest_worker:skipped_on_demand" in script
        assert "tquant-analytics-worker-mysql" in script
        assert "analytics_worker_readyz:ok" in script
        assert "DEPLOY_WITH_ANALYTICS_WORKER" in script
        assert "analytics_worker:skipped_on_demand" in script or "analytics_worker_readyz:skipped_on_demand" in script
    assert "wait_for_container" in deploy_script
    assert "wait_for_container" in quick_script


def test_runtime_worker_supports_embedded_scheduler_grey_flag() -> None:
    runtime_worker = read_repo_file("backend/app/workers/runtime_worker.py")
    background_jobs = read_repo_file("backend/app/runtime/background_jobs.py")
    config = read_repo_file("backend/app/core/config.py")

    assert "runtime_worker_embed_scheduler: bool = False" in config
    assert "runtime_scheduler_leader_lock_ttl_seconds: int = 60" in config
    assert "if settings.runtime_worker_embed_scheduler:" in runtime_worker
    assert "start_runtime_background_jobs()" in runtime_worker
    assert "shutdown_runtime_background_jobs()" in runtime_worker
    assert "_worker_embedded_scheduler_enabled" in background_jobs
    assert 'component="runtime-scheduler"' in background_jobs
    assert "runtime-worker-embedded-scheduler" in background_jobs
    assert 'name="runtime_scheduler_heartbeat"' in background_jobs


def test_runbooks_document_independent_health_and_rollback_commands() -> None:
    topology = read_repo_file("docs/operations/deployment-topology-runbook.md")
    worker = read_repo_file("docs/operations/worker-runbook.md")
    production = read_repo_file("PRODUCTION_RUNBOOK.md")

    for text in (topology, worker, production):
        assert "runtime-worker" in text
        assert "runtime-scheduler" in text
        assert "analytics-worker" in text
        assert "backtest-worker" in text
    assert "Web does not recompute 24-month reports" in topology
    assert "Restart runtime worker" in topology
    assert "Restart scheduler" in topology
    assert "Restart analytics worker" in topology
    assert "Restart backtest worker" in topology
    assert "scripts/run_platform_component.sh analytics-worker --once" in worker
    assert "`portfolio_backtest_metrics` remains the final portfolio fact source" in worker
