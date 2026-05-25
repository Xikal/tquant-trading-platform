from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.routes import bff
from app.models.base import Base
from app.models.entities import User
from app.models.schema_defs.market import MarketBreadthResponse, SectorRelativeStrengthResponse
from app.models.schema_defs.monitor import MonitorSnapshotResponse


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

    response = bff._build_monitor_workspace(
        db,
        current_user=DetachedUser(9),
        priority_limit=12,
        sector_limit=8,
        per_sector_limit=8,
        hedge_limit=4,
    )

    assert response.paired_hedge is not None
    assert response.partial_errors == []


def test_monitor_workspace_uses_attached_db_for_market_breadth_and_detached_user(monkeypatch) -> None:
    db = _db_with_user(11)
    calls: dict[str, object] = {}

    def fake_market_breadth(*, db):
        calls["market_breadth_db"] = db
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
    assert calls["paired_user_id"] == 11
