from __future__ import annotations


def test_runtime_scheduler_starts_jobs_and_waits_for_shutdown(monkeypatch):
    from app.workers import runtime_scheduler

    calls: list[str] = []

    monkeypatch.setattr(runtime_scheduler.signal, "signal", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(runtime_scheduler, "_record_scheduler_heartbeat", lambda **_kwargs: None)
    monkeypatch.setattr(runtime_scheduler, "start_runtime_background_jobs", lambda: calls.append("start"))
    monkeypatch.setattr(runtime_scheduler, "shutdown_runtime_background_jobs", lambda timeout=30: calls.append(f"shutdown:{timeout}"))
    monkeypatch.setattr(runtime_scheduler._stop_event, "wait", lambda timeout=30: calls.append(f"wait:{timeout}") or True)

    runtime_scheduler.main()

    assert calls == ["start", "wait:30", "shutdown:30"]
