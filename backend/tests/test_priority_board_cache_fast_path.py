from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import screeners
from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.schemas import LowBuyPriorityBoardResponse
from app.services.low_buy.priority_board import LowBuyPriorityBoardMixin


class _Service(LowBuyPriorityBoardMixin):
    _priority_response_cache_ttl = 1
    _priority_base_cache_ttl = 1

    def __init__(self) -> None:
        self._priority_response_cache = {}
        self._priority_base_cache = {}
        import threading

        self._cache_lock = threading.Lock()
        self.rebuild_count = 0

    def _build_priority_base_snapshot(self, db, limit):  # noqa: ANN001
        self.rebuild_count += 1
        raise AssertionError("request fast path must not rebuild priority board")


def _board() -> LowBuyPriorityBoardResponse:
    return LowBuyPriorityBoardResponse(
        as_of_date="2026-05-26",
        latest_trade_date="2026-05-26",
        latest_available_trade_date="2026-05-27",
        updated_at="2026-05-27 09:30:00",
        total_candidates=0,
        items=[],
        snapshot_warning="缓存已过期。",
    )


def test_priority_board_fast_path_returns_latest_stale_without_rebuild(monkeypatch):
    service = _Service()
    stale = _board()

    def fake_cache(_service, _key, *, allow_stale=False):
        return stale if allow_stale else None

    monkeypatch.setattr("app.services.low_buy.priority_board.get_priority_response_cache", fake_cache)
    queued = []
    monkeypatch.setattr(
        "app.services.low_buy.priority_board.enqueue_low_buy_materialization",
        lambda db, reason, commit=False: queued.append((reason, commit)),
    )
    monkeypatch.setattr("app.services.low_buy.priority_board.published_low_buy_trade_date", lambda db: "2026-05-27")

    result = service.priority_board(SimpleNamespace(), limit=12)

    assert result.latest_trade_date == "2026-05-26"
    assert result.data_quality == "stale"
    assert "refresh_queued" in result.data_quality_tags
    assert "后台刷新" in result.snapshot_warning
    assert queued == [("priority_board_cache_miss", False)]
    assert service.rebuild_count == 0


def test_priority_board_async_empty_returns_placeholder_and_queues(monkeypatch):
    service = _Service()
    monkeypatch.setattr(
        "app.services.low_buy.priority_board.get_priority_response_cache",
        lambda _service, _key, *, allow_stale=False: None,
    )
    queued = []
    monkeypatch.setattr(
        "app.services.low_buy.priority_board.enqueue_low_buy_materialization",
        lambda db, reason, commit=False: queued.append(reason),
    )
    monkeypatch.setattr("app.services.low_buy.priority_board.published_low_buy_trade_date", lambda db: "2026-05-27")

    result = service.priority_board(SimpleNamespace(), limit=12)

    assert result.latest_trade_date == ""
    assert result.data_quality == "unavailable"
    assert "cache_empty" in result.data_quality_tags
    assert queued == ["priority_board_cache_empty"]
    assert service.rebuild_count == 0


def test_priority_board_route_passes_refresh_mode(monkeypatch):
    calls = []

    def fake_priority_board(*, db, limit, refresh_mode, **_kwargs):  # noqa: ANN001
        calls.append((limit, refresh_mode))
        return _board()

    monkeypatch.setattr(screeners.low_buy_screener, "priority_board", fake_priority_board)
    monkeypatch.setattr(
        "app.api.routes.screeners.UserSectorPreferenceService",
        lambda db: SimpleNamespace(get_excluded_sector_set=lambda user_id: set()),
    )
    app = FastAPI()
    app.include_router(screeners.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, username="tester", is_active=True)
    app.dependency_overrides[get_db] = lambda: SimpleNamespace()

    response = TestClient(app).get("/api/screeners/low-buy/priority-board?limit=12&refresh=async")

    assert response.status_code == 200
    assert calls == [(12, "async")]
