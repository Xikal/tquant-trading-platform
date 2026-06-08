from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.entities import SystemSetting
from app.services import frontend_next_cutover


def test_frontend_next_cutover_runtime_setting_overrides_env(monkeypatch):
    engine = create_engine("sqlite://", future=True, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)
    with Session() as db:
        db.add(
            SystemSetting(
                key=frontend_next_cutover.FRONTEND_NEXT_MONITOR_CUTOVER_SETTING_KEY,
                value="true",
            )
        )
        db.commit()

    monkeypatch.setattr(frontend_next_cutover, "SessionLocal", Session)

    class _Settings:
        frontend_next_monitor_cutover_enabled = False
        frontend_next_cutover_paths = ""

    monkeypatch.setattr(frontend_next_cutover, "get_settings", lambda: _Settings())
    frontend_next_cutover.clear_frontend_next_cutover_cache()

    assert frontend_next_cutover.frontend_next_monitor_cutover_enabled() is True
    assert frontend_next_cutover.frontend_next_cutover_paths() == frozenset({"monitor"})


def test_frontend_next_cutover_invalid_runtime_setting_falls_back_to_env(monkeypatch):
    engine = create_engine("sqlite://", future=True, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)
    with Session() as db:
        db.add(
            SystemSetting(
                key=frontend_next_cutover.FRONTEND_NEXT_MONITOR_CUTOVER_SETTING_KEY,
                value="maybe",
            )
        )
        db.commit()

    monkeypatch.setattr(frontend_next_cutover, "SessionLocal", Session)

    class _Settings:
        frontend_next_monitor_cutover_enabled = True
        frontend_next_cutover_paths = ""

    monkeypatch.setattr(frontend_next_cutover, "get_settings", lambda: _Settings())
    frontend_next_cutover.clear_frontend_next_cutover_cache()

    assert frontend_next_cutover.frontend_next_monitor_cutover_enabled() is True


def test_frontend_next_cutover_paths_parse_allowlist(monkeypatch):
    class _Settings:
        frontend_next_monitor_cutover_enabled = False
        frontend_next_cutover_paths = "/, monitor, monitor/market, paper, unknown, /settings/"

    monkeypatch.setattr(frontend_next_cutover, "get_settings", lambda: _Settings())
    frontend_next_cutover.clear_frontend_next_cutover_cache()

    assert frontend_next_cutover.frontend_next_cutover_paths() == frozenset(
        {"", "monitor", "monitor/market", "paper", "settings"}
    )


def test_frontend_next_cutover_paths_all(monkeypatch):
    class _Settings:
        frontend_next_monitor_cutover_enabled = False
        frontend_next_cutover_paths = "all"

    monkeypatch.setattr(frontend_next_cutover, "get_settings", lambda: _Settings())
    frontend_next_cutover.clear_frontend_next_cutover_cache()

    assert frontend_next_cutover.frontend_next_cutover_paths() == frontend_next_cutover.SUPPORTED_CUTOVER_PATHS
    assert "" in frontend_next_cutover.frontend_next_cutover_paths()
