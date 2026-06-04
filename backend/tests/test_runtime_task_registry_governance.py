from __future__ import annotations

from app.services.tasks.registry import RUNTIME_TASK_REGISTRY, TaskDefinition, analytics_task_registry
from app.workers.heavy_research_tasks import HEAVY_RESEARCH_TASK_TYPES
from app.workers.runtime_worker import RUNTIME_WORKER_TASK_TYPES


def test_runtime_task_registry_definitions_are_complete() -> None:
    assert RUNTIME_TASK_REGISTRY
    for task_type, definition in RUNTIME_TASK_REGISTRY.items():
        assert isinstance(definition, TaskDefinition)
        assert definition.task_type == task_type
        assert definition.owner_role in {"quant", "data", "devops"}
        assert definition.worker in {"runtime", "analytics", "backtest", "scheduler", "web"}
        assert definition.retry_policy
        assert definition.max_attempts >= 1
        assert definition.artifact_kind in {"none", "metrics", "snapshot", "report", "parquet"}
        assert isinstance(definition.idempotency_required, bool)
        assert definition.expected_runtime_p95_ms > 0


def test_runtime_worker_task_types_match_registry_runtime_scope() -> None:
    runtime_registry = {
        task_type
        for task_type, definition in RUNTIME_TASK_REGISTRY.items()
        if definition.worker == "runtime"
    }

    assert set(RUNTIME_WORKER_TASK_TYPES) == runtime_registry
    assert set(HEAVY_RESEARCH_TASK_TYPES).issubset(runtime_registry)


def test_analytics_handlers_match_registry_analytics_scope() -> None:
    analytics_registry = {
        task_type
        for task_type, definition in RUNTIME_TASK_REGISTRY.items()
        if definition.worker == "analytics"
    }

    assert set(analytics_task_registry().task_types()) == analytics_registry


def test_no_runtime_task_registry_duplicate_or_unknown_worker() -> None:
    assert len(RUNTIME_TASK_REGISTRY) == len(set(RUNTIME_TASK_REGISTRY))
    assert "noop" in RUNTIME_TASK_REGISTRY
    assert "analytics_quality_check" in RUNTIME_TASK_REGISTRY
    assert RUNTIME_TASK_REGISTRY["noop"].worker == "runtime"
    assert RUNTIME_TASK_REGISTRY["analytics_quality_check"].worker == "analytics"
