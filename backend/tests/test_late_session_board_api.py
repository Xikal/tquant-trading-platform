from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import screeners
from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.schema_defs.phase4 import RuntimeTaskOut
from app.models.schema_defs.late_session_board import (
    LateSessionBoardItemOut,
    LateSessionBoardResponse,
    LateSessionBoardStatus,
    LateSessionItemState,
    LateSessionSnapshotSlot,
)
from app.models.schemas import LowBuyPriorityBoardItemOut, LowBuyPriorityBoardResponse


def _app_with_user(user: object | None = None) -> FastAPI:
    app = FastAPI()
    app.include_router(screeners.router, prefix="/api")
    if user is not None:
        app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: SimpleNamespace()
    return app


def _board() -> LowBuyPriorityBoardResponse:
    return LowBuyPriorityBoardResponse(
        as_of_date="2026-06-13",
        latest_trade_date="2026-06-13",
        latest_available_trade_date="2026-06-13",
        updated_at="2026-06-13 14:50:00",
        total_candidates=1,
        market_gate_decision="allow",
        market_state="repair",
        items=[
            LowBuyPriorityBoardItemOut(
                symbol="000001",
                name="平安银行",
                strategy_key="first_board",
                strategy_title="首板回调",
                priority_score=88,
                production_score=82,
                buy_signal_state="watch",
                latest_price=10.16,
                change_pct=0.8,
                quote_timestamp="2026-06-13 14:50:00",
                entry_zone_low=9.8,
                entry_zone_high=10.2,
                stop_loss=9.5,
            )
        ],
    )


def _user() -> SimpleNamespace:
    return SimpleNamespace(id=1, username="tester", is_active=True, role="user")


def test_late_session_board_requires_login() -> None:
    response = TestClient(_app_with_user()).get("/api/screeners/low-buy/late-session-board")

    assert response.status_code == 401


def test_late_session_board_cache_mode_does_not_trigger_full_scan(monkeypatch) -> None:
    calls: list[str] = []

    def fake_priority_board(*, db, limit, refresh_mode, strategy_variant, **_kwargs):  # noqa: ANN001
        calls.append(f"{limit}:{refresh_mode}:{strategy_variant}")
        return _board()

    monkeypatch.setattr(screeners.low_buy_screener, "priority_board", fake_priority_board)
    monkeypatch.setattr(
        screeners,
        "UserSectorPreferenceService",
        lambda db: SimpleNamespace(get_excluded_sector_set=lambda user_id: set()),
    )
    monkeypatch.setattr(
        screeners,
        "filter_priority_board_response_for_user",
        lambda result, user_id, excluded_sectors: result,
    )

    response = TestClient(_app_with_user(_user())).get(
        "/api/screeners/low-buy/late-session-board?limit=12&refresh=cache"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["snapshot_slot"] == "latest"
    assert body["items"][0]["symbol"] == "000001"
    assert calls == ["30:cache:baseline"]


def test_late_session_board_cache_mode_uses_stored_snapshot_when_available(monkeypatch) -> None:
    enqueued: list[str] = []
    cached = LateSessionBoardResponse(
        trade_date="2026-06-13",
        snapshot_slot=LateSessionSnapshotSlot.FINAL_1457,
        generated_at=datetime(2026, 6, 13, 14, 57),
        status=LateSessionBoardStatus.OK,
        items=[
            LateSessionBoardItemOut(
                symbol="000002",
                name="万科A",
                late_session_state=LateSessionItemState.LATE_CONFIRMED,
                late_session_score=83,
                snapshot_slot=LateSessionSnapshotSlot.FINAL_1457,
            )
        ],
    )
    monkeypatch.setattr(screeners.low_buy_screener, "priority_board", lambda **_kwargs: _board())
    monkeypatch.setattr(
        screeners,
        "UserSectorPreferenceService",
        lambda db: SimpleNamespace(get_excluded_sector_set=lambda user_id: set()),
    )
    monkeypatch.setattr(
        screeners,
        "filter_priority_board_response_for_user",
        lambda result, user_id, excluded_sectors: result,
    )
    monkeypatch.setattr(screeners, "load_distributed_late_session_board_snapshot", lambda key: cached)
    monkeypatch.setattr(
        screeners,
        "enqueue_runtime_task",
        lambda *args, **kwargs: enqueued.append(kwargs.get("task_type", "")),
    )

    response = TestClient(_app_with_user(_user())).get(
        "/api/screeners/low-buy/late-session-board?refresh=cache&slot=final_1457"
    )

    assert response.status_code == 200
    assert response.json()["items"][0]["symbol"] == "000002"
    assert response.json()["refresh_mode"] == "cache"
    assert enqueued == []


def test_late_session_board_async_mode_enqueues_light_task_only(monkeypatch) -> None:
    enqueued: list[tuple[str, dict[str, object], str]] = []

    monkeypatch.setattr(screeners.low_buy_screener, "priority_board", lambda **_kwargs: _board())
    monkeypatch.setattr(
        screeners,
        "UserSectorPreferenceService",
        lambda db: SimpleNamespace(get_excluded_sector_set=lambda user_id: set()),
    )
    monkeypatch.setattr(
        screeners,
        "filter_priority_board_response_for_user",
        lambda result, user_id, excluded_sectors: result,
    )

    def fake_enqueue(db, *, task_type, payload, idempotency_key, **_kwargs):  # noqa: ANN001
        enqueued.append((task_type, payload, idempotency_key))
        return RuntimeTaskOut(
            id=7,
            task_type=task_type,
            status="queued",
            payload=payload,
            created_at=datetime(2026, 6, 13, 14, 50),
            updated_at=datetime(2026, 6, 13, 14, 50),
        )

    monkeypatch.setattr(screeners, "enqueue_runtime_task", fake_enqueue)

    response = TestClient(_app_with_user(_user())).get(
        "/api/screeners/low-buy/late-session-board?refresh=async&slot=preview_1450"
    )

    assert response.status_code == 200
    assert response.json()["degradation_reason"] in {"refresh_queued", "minute_data_missing"}
    assert enqueued == [
        (
            "late_session_recommendation_refresh",
            {"slot": "preview_1450", "strategy_variant": "baseline", "limit": 12, "source_limit": 30, "reason": "api_async"},
            "late_session_recommendation_refresh:2026-06-13:preview_1450",
        )
    ]


def test_late_session_board_sync_mode_downgrades_to_async_without_admin(monkeypatch) -> None:
    enqueued: list[str] = []
    monkeypatch.setattr(screeners.low_buy_screener, "priority_board", lambda **_kwargs: _board())
    monkeypatch.setattr(
        screeners,
        "UserSectorPreferenceService",
        lambda db: SimpleNamespace(get_excluded_sector_set=lambda user_id: set()),
    )
    monkeypatch.setattr(
        screeners,
        "filter_priority_board_response_for_user",
        lambda result, user_id, excluded_sectors: result,
    )
    monkeypatch.setattr(
        screeners,
        "enqueue_runtime_task",
        lambda db, *, task_type, payload, idempotency_key, **_kwargs: enqueued.append(task_type)
        or RuntimeTaskOut(
            id=8,
            task_type=task_type,
            status="queued",
            payload=payload,
            created_at=datetime(2026, 6, 13, 14, 55),
            updated_at=datetime(2026, 6, 13, 14, 55),
        ),
    )

    response = TestClient(_app_with_user(_user())).get(
        "/api/screeners/low-buy/late-session-board?refresh=sync&slot=snapshot_1455"
    )

    assert response.status_code == 200
    assert response.json()["refresh_mode"] == "async"
    assert enqueued == ["late_session_recommendation_refresh"]


def test_late_session_board_degraded_response_has_complete_schema(monkeypatch) -> None:
    monkeypatch.setattr(screeners.low_buy_screener, "priority_board", lambda **_kwargs: _board())
    monkeypatch.setattr(
        screeners,
        "UserSectorPreferenceService",
        lambda db: SimpleNamespace(get_excluded_sector_set=lambda user_id: set()),
    )
    monkeypatch.setattr(
        screeners,
        "filter_priority_board_response_for_user",
        lambda result, user_id, excluded_sectors: result,
    )

    response = TestClient(_app_with_user(_user())).get("/api/screeners/low-buy/late-session-board")

    assert response.status_code == 200
    body = response.json()
    assert {"trade_date", "snapshot_slot", "generated_at", "status", "items", "data_quality_tags"} <= set(body)
    assert {"late_session_state", "late_session_score", "reject_reasons", "snapshot_slot"} <= set(body["items"][0])
