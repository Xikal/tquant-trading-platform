from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.routes import bff
from app.models.base import Base
from app.models.entities import User
from fastapi import HTTPException

from app.models.schema_defs.market import MarketBreadthResponse, MarketReviewStatusOut, SectorRelativeStrengthResponse
from app.models.schema_defs.monitor import MonitorSnapshotResponse
from app.models.schema_defs.settings import RuntimeStatusResponse


def _db_with_user(user_id: int = 9):
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, future=True)
    db = Session()
    db.add(
        User(
            id=user_id,
            username=f"researcher{user_id}",
            password_hash="x",
            is_active=True,
            roles="backtest_research",
        )
    )
    db.commit()
    return db


class DetachedUser:
    def __init__(self, user_id: int) -> None:
        self.id = user_id

    @property
    def roles(self):
        raise RuntimeError("DetachedInstanceError")


def test_monitor_workspace_paired_hedge_reloads_detached_user(monkeypatch) -> None:
    db = _db_with_user()

    monkeypatch.setattr(
        bff,
        "build_monitor_snapshot",
        lambda *args, **kwargs: MonitorSnapshotResponse(updated_at="2026-05-25 10:00:00"),
    )
    monkeypatch.setattr(
        bff,
        "market_breadth",
        lambda *args, **kwargs: MarketBreadthResponse(updated_at="2026-05-25 10:00:00"),
    )
    monkeypatch.setattr(
        bff,
        "sector_relative_strength",
        lambda *args: SectorRelativeStrengthResponse(updated_at="2026-05-25 10:00:00"),
    )
    monkeypatch.setattr(
        bff,
        "paired_hedge_research",
        lambda limit, current_user, _db: {"updated_at": "2026-05-25 10:00:00", "total": limit, "ideas": []},
    )
    monkeypatch.setattr(
        bff,
        "build_market_review_summary",
        lambda *_args, **_kwargs: (
            MarketReviewStatusOut(
                trade_date="2026-05-25",
                status="midday_ready",
                status_text="今日市场午盘复盘已生成，等待收盘复盘",
                has_midday=True,
                next_trigger_at="2026-05-25 15:05",
                risk_alert_count=0,
                suggested_action="午后控制追高",
            ),
            [],
        ),
    )
    monkeypatch.setattr(bff, "list_hourly_snapshot_history", lambda *_args, **_kwargs: [])

    response = bff._build_monitor_workspace(
        db,
        current_user=DetachedUser(9),
        priority_limit=12,
        sector_limit=8,
        per_sector_limit=8,
        hedge_limit=4,
        include_runtime=True,
    )

    assert response.paired_hedge is not None
    assert response.market_pulse is not None
    assert response.review_status is not None
    assert response.review_status.suggested_action == "午后控制追高"
    assert response.partial_errors == []


def test_monitor_workspace_bundles_hourly_history_and_admin_runtime(monkeypatch) -> None:
    db = _db_with_user(13)
    db.query(User).filter(User.id == 13).update({"roles": "admin"})
    db.commit()
    monkeypatch.setattr(
        bff,
        "build_monitor_snapshot",
        lambda *args, **kwargs: MonitorSnapshotResponse(updated_at="2026-05-25 10:00:00"),
    )
    monkeypatch.setattr(bff, "market_breadth", lambda *args, **kwargs: MarketBreadthResponse(updated_at="2026-05-25 10:00:00"))
    monkeypatch.setattr(bff, "sector_relative_strength", lambda *args: SectorRelativeStrengthResponse(updated_at="2026-05-25 10:00:00"))
    monkeypatch.setattr(bff, "paired_hedge_research", lambda *args: {"updated_at": "2026-05-25 10:00:00", "ideas": []})
    monkeypatch.setattr(bff, "build_market_review_summary", lambda *_args, **_kwargs: (None, []))
    monkeypatch.setattr(
        bff,
        "list_hourly_snapshot_history",
        lambda *_args, **_kwargs: [{"id": 1, "trade_date": "2026-06-03", "snapshot_bucket": "10:30"}],
    )
    monkeypatch.setattr(
        bff.SettingsRuntimeDiagnosticsService,
        "build_status",
        lambda self: RuntimeStatusResponse(
            app_name="test",
            api_prefix="/api",
            database_backend="sqlite",
            database_url_masked="sqlite:///test",
            runtime_env_path="/tmp/runtime.env",
            runtime_env_exists=False,
            runtime_database_override=False,
            frontend_dist_path="/tmp/dist/index.html",
            frontend_dist_ready=True,
            llm_configured=False,
            data_source="test",
            data_source_base_url="",
            cors_origins=[],
            ready_checks={},
        ),
    )

    response = bff._build_monitor_workspace(
        db,
        current_user=User(id=13, username="admin", password_hash="x", is_active=True, roles="admin"),
        priority_limit=12,
        sector_limit=8,
        per_sector_limit=8,
        hedge_limit=4,
        include_runtime=True,
    )

    assert len(response.hourly_snapshot_history) == 1
    assert response.runtime is not None
    assert response.runtime.app_name == "test"


def test_monitor_workspace_uses_attached_db_for_market_breadth_and_detached_user(monkeypatch) -> None:
    db = _db_with_user(11)
    calls: dict[str, object] = {}

    def fake_market_breadth(*, db, realtime=True):
        calls["market_breadth_db"] = db
        calls["market_breadth_realtime"] = realtime
        return MarketBreadthResponse(updated_at="2026-05-25 10:00:00")

    def fake_paired_hedge(limit, current_user, _db):
        calls["paired_user_id"] = getattr(current_user, "id", None)
        return {"updated_at": "2026-05-25 10:00:00", "total": limit, "ideas": []}

    monkeypatch.setattr(
        bff,
        "build_monitor_snapshot",
        lambda *args, **kwargs: MonitorSnapshotResponse(updated_at="2026-05-25 10:00:00"),
    )
    monkeypatch.setattr(bff, "market_breadth", fake_market_breadth)
    monkeypatch.setattr(
        bff,
        "sector_relative_strength",
        lambda *args: SectorRelativeStrengthResponse(updated_at="2026-05-25 10:00:00"),
    )
    monkeypatch.setattr(bff, "paired_hedge_research", fake_paired_hedge)

    response = bff._build_monitor_workspace(
        db,
        current_user=DetachedUser(11),
        priority_limit=12,
        sector_limit=8,
        per_sector_limit=8,
        hedge_limit=4,
    )

    assert response.market_breadth is not None
    assert response.paired_hedge is not None
    assert response.partial_errors == []
    assert calls["market_breadth_db"] is db
    assert calls["market_breadth_realtime"] is False
    assert calls["paired_user_id"] == 11


def test_monitor_workspace_hides_forbidden_paired_hedge_for_standard_user(monkeypatch) -> None:
    db = _db_with_user(12)

    monkeypatch.setattr(
        bff,
        "build_monitor_snapshot",
        lambda *args, **kwargs: MonitorSnapshotResponse(updated_at="2026-05-25 10:00:00"),
    )
    monkeypatch.setattr(
        bff,
        "market_breadth",
        lambda *args, **kwargs: MarketBreadthResponse(updated_at="2026-05-25 10:00:00"),
    )
    monkeypatch.setattr(
        bff,
        "sector_relative_strength",
        lambda *args: SectorRelativeStrengthResponse(updated_at="2026-05-25 10:00:00"),
    )
    monkeypatch.setattr(
        bff,
        "paired_hedge_research",
        lambda *args: (_ for _ in ()).throw(HTTPException(status_code=403, detail="账号未开通研究权限")),
    )

    response = bff._build_monitor_workspace(
        db,
        current_user=DetachedUser(12),
        priority_limit=12,
        sector_limit=8,
        per_sector_limit=8,
        hedge_limit=4,
    )

    assert response.monitor_snapshot is not None
    assert response.market_breadth is not None
    assert response.sector_relative_strength is not None
    assert response.paired_hedge is None
    assert response.partial_errors == []
