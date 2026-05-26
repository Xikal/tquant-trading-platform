from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.models.base import Base
from app.models.entities import RuntimeTask, SystemSetting, User, UserSession, PaperAccount, BacktestRun
from app.services.db_admin_service import DatabaseAdminService, MODEL_COPY_ORDER
from app.services.settings_runtime import SettingsRuntimeDiagnosticsService


def test_model_copy_order_covers_core_application_tables() -> None:
    copied_models = set(MODEL_COPY_ORDER)

    assert User in copied_models
    assert UserSession in copied_models
    assert PaperAccount in copied_models
    assert BacktestRun in copied_models
    assert RuntimeTask in copied_models


def test_migration_rolls_back_target_when_copy_fails(tmp_path: Path) -> None:
    source_url = f"sqlite:///{tmp_path / 'source.db'}"
    target_url = f"sqlite:///{tmp_path / 'target.db'}"
    source_engine = create_engine(source_url, future=True)
    target_engine = create_engine(target_url, future=True)
    Base.metadata.create_all(source_engine)
    Base.metadata.create_all(target_engine)
    SessionLocal = sessionmaker(future=True)

    with SessionLocal(bind=source_engine) as source:
        source.add_all([
            SystemSetting(key="runtime_one", value="source-1"),
            SystemSetting(key="runtime_two", value="source-2"),
        ])
        source.commit()
    with SessionLocal(bind=target_engine) as target:
        target.add(SystemSetting(key="runtime_existing", value="target-keep"))
        target.commit()

    original_merge = Session.merge
    merge_calls = 0

    def fail_on_second_merge(self: Session, instance: object, *args: object, **kwargs: object) -> object:
        nonlocal merge_calls
        if isinstance(instance, SystemSetting):
            merge_calls += 1
            if merge_calls == 2:
                raise RuntimeError("copy failed")
        return original_merge(self, instance, *args, **kwargs)

    with patch.object(Session, "merge", fail_on_second_merge):
        with pytest.raises(RuntimeError, match="copy failed"):
            DatabaseAdminService().migrate_data(source_url, target_url, overwrite=True)

    with SessionLocal(bind=target_engine) as target:
        settings = target.execute(select(SystemSetting)).scalars().all()

    assert [(item.key, item.value) for item in settings] == [("runtime_existing", "target-keep")]


def test_runtime_status_reports_runtime_env_consistency(tmp_path: Path, monkeypatch) -> None:
    runtime_env_path = tmp_path / "runtime.env"
    runtime_env_path.write_text(
        'DATABASE_URL="sqlite:///runtime.db"\nLLM_API_KEY="plain-secret"\n',
        encoding="utf-8",
    )
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, future=True)

    class FakeAdminService(DatabaseAdminService):
        def check_connection(self, database_url: str):  # type: ignore[override]
            return object()

        def _build_engine_bundle(self, database_url: str):  # type: ignore[override]
            class Bundle:
                engine = create_engine("sqlite:///:memory:", future=True)

            return Bundle()

    monkeypatch.setattr("app.services.settings_runtime.RUNTIME_ENV_PATH", runtime_env_path)
    monkeypatch.setattr(
        "app.services.settings_runtime.get_settings",
        lambda: type(
            "Settings",
            (),
            {
                "app_name": "TQuant",
                "api_prefix": "/api",
                "database_url": "sqlite:///current.db",
                "cors_origins": [],
            },
        )(),
    )

    with SessionLocal() as db:
        status = SettingsRuntimeDiagnosticsService(db, FakeAdminService()).build_status()

    assert status.runtime_database_override is True
    assert status.runtime_database_matches_settings is False
    assert status.runtime_llm_secret_persisted is True
    assert status.ready_checks["runtime_consistency"] is False
    assert status.settings_consistency_status == "warning"
