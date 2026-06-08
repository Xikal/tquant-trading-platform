from __future__ import annotations

import time
from types import SimpleNamespace

from app.models.schema_defs.settings import RuntimeStatusResponse, SettingsPayload
from app.services.bff import settings_workspace


def test_settings_workspace_degrades_slow_admin_sources(monkeypatch) -> None:
    class FakeSettingsService:
        def __init__(self, db) -> None:
            self.db = db

        def get_public_payload(self, **_kwargs) -> SettingsPayload:
            return SettingsPayload(data_source="akshare_eastmoney")

    class FakeSectorPreferenceService:
        def __init__(self, db) -> None:
            self.db = db

        def build_response(self, user_id: int) -> dict:
            return {"available_sectors": [], "excluded_sectors": [], "excluded_count": 0, "updated_at": "2026-06-08 09:30:00"}

    class SlowRuntimeDiagnosticsService:
        def __init__(self, db) -> None:
            self.db = db

        def build_status(self) -> RuntimeStatusResponse:
            time.sleep(0.05)
            return RuntimeStatusResponse()

    monkeypatch.setattr(settings_workspace, "SettingsService", FakeSettingsService)
    monkeypatch.setattr(settings_workspace, "UserSectorPreferenceService", FakeSectorPreferenceService)
    monkeypatch.setattr(settings_workspace, "build_low_buy_strategy_governance", lambda _db: None)
    monkeypatch.setattr(settings_workspace, "SettingsRuntimeDiagnosticsService", SlowRuntimeDiagnosticsService)
    monkeypatch.setattr(settings_workspace, "SettingsFactorWeightsService", lambda: SimpleNamespace(build_response=lambda: None))
    monkeypatch.setattr(settings_workspace, "build_admin_task_snapshot", lambda: {})
    monkeypatch.setattr(settings_workspace, "build_admin_metrics_snapshot", lambda _db: {})
    monkeypatch.setattr(settings_workspace, "SETTINGS_WORKSPACE_SOURCE_TIMEOUT_MS", {"runtime": 10})

    started = time.perf_counter()
    response = settings_workspace.build_settings_workspace(
        object(),
        current_user=SimpleNamespace(id=7),
        include_admin=True,
    )
    elapsed = time.perf_counter() - started

    assert elapsed < 0.04
    assert response.admin_enabled is True
    assert response.settings is not None
    assert response.sector_exclusions is not None
    assert response.runtime is None
    assert len(response.partial_errors) == 1
    assert response.partial_errors[0].source == "runtime"
    assert response.partial_errors[0].reason == "timeout"
