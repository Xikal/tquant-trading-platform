from __future__ import annotations

from types import SimpleNamespace

from app.services.local_desktop_status import build_local_desktop_status


def test_local_desktop_status_marks_redis_unknown_when_not_configured(monkeypatch) -> None:
    monkeypatch.setattr("app.services.local_desktop_status.ping_database", lambda: None)
    monkeypatch.setattr("app.services.local_desktop_status.get_distributed_cache_client", lambda: None)
    monkeypatch.setattr(
        "app.services.local_desktop_status.get_settings",
        lambda: SimpleNamespace(app_name="TQuant", app_environment="local", redis_url="", database_url="sqlite:///local.db"),
    )
    response = build_local_desktop_status(db=SimpleNamespace(), project_root="/tmp/tquant-local")

    components = {item.name: item for item in response.components}

    assert components["backend"].status == "ok"
    assert components["mysql"].status == "ok"
    assert components["redis"].status == "unknown"
    assert response.safety == {
        "deploy_allowed": False,
        "restart_production_allowed": False,
        "cleanup_allowed": False,
        "auto_trade_allowed": False,
        "strategy_mutation_allowed": False,
    }


def test_local_desktop_status_keeps_overall_response_when_database_ping_fails(monkeypatch) -> None:
    def fail_ping() -> None:
        raise RuntimeError("db password=secret should not leak")

    monkeypatch.setattr("app.services.local_desktop_status.ping_database", fail_ping)
    monkeypatch.setattr("app.services.local_desktop_status.get_distributed_cache_client", lambda: None)
    monkeypatch.setattr(
        "app.services.local_desktop_status.get_settings",
        lambda: SimpleNamespace(app_name="TQuant", app_environment="local", redis_url="", database_url="mysql://user:pass@localhost/db"),
    )

    response = build_local_desktop_status(db=SimpleNamespace(), project_root="/tmp/tquant-local")
    payload = response.model_dump(mode="json")
    components = {item.name: item for item in response.components}

    assert components["mysql"].status == "error"
    assert "secret" not in str(payload).lower()
    assert "password" not in str(payload).lower()
    assert "mysql://user:pass" not in str(payload)


def test_local_desktop_status_does_not_enqueue_runtime_tasks(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr("app.services.local_desktop_status.ping_database", lambda: None)
    monkeypatch.setattr("app.services.local_desktop_status.get_distributed_cache_client", lambda: None)
    monkeypatch.setattr(
        "app.services.local_desktop_status.get_settings",
        lambda: SimpleNamespace(app_name="TQuant", app_environment="local", redis_url="", database_url="sqlite:///local.db"),
    )

    class QueueStub:
        def __init__(self, _db) -> None:
            pass

        def enqueue(self, _payload) -> None:
            calls.append("enqueue")

        def workers(self):
            return SimpleNamespace(items=[], total=0)

        def summary(self):
            return SimpleNamespace(queued=0, running=0, failed=0)

    monkeypatch.setattr("app.services.local_desktop_status.RuntimeTaskQueue", QueueStub)

    response = build_local_desktop_status(db=SimpleNamespace(), project_root="/tmp/tquant-local")

    assert response.components
    assert calls == []


def test_local_desktop_status_includes_read_only_launch_guides(monkeypatch) -> None:
    monkeypatch.setattr("app.services.local_desktop_status.ping_database", lambda: None)
    monkeypatch.setattr("app.services.local_desktop_status.get_distributed_cache_client", lambda: None)
    monkeypatch.setattr(
        "app.services.local_desktop_status.get_settings",
        lambda: SimpleNamespace(app_name="TQuant", app_environment="local", redis_url="", database_url="sqlite:///local.db"),
    )

    response = build_local_desktop_status(db=SimpleNamespace(), project_root="/Users/j/Documents/gupiao")
    commands = {item.key: item.command for item in response.launch_guides}
    guide_text = str([item.model_dump(mode="json") for item in response.launch_guides]).lower()

    assert commands["web"] == "scripts/run_platform_component.sh web"
    assert commands["runtime_worker"] == "scripts/run_platform_component.sh runtime-worker"
    assert commands["runtime_scheduler"] == "scripts/run_platform_component.sh scheduler"
    assert commands["analytics_worker"] == "scripts/run_platform_component.sh analytics-worker"
    assert "docker compose" not in guide_text
    assert "deploy" not in guide_text
    assert "restart" not in guide_text
