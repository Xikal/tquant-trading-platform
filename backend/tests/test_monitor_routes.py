from __future__ import annotations

import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import monitor
from app.core.auth import get_current_user
from app.core.database import get_db
from app.services import monitor_snapshot_service
from app.services.monitor_snapshot_cache import MonitorSnapshotCacheHit


def _override_user():
    class UserStub:
        id = 1
        username = "tester"
        is_active = True

    return UserStub()


def _override_db():
    yield object()


class MonitorRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_list_rows = monitor_snapshot_service.list_user_watchlist_rows
        self.original_signature = monitor_snapshot_service.rows_signature
        self.original_read_cache = monitor_snapshot_service.read_monitor_snapshot_cache
        self.original_enqueue = monitor_snapshot_service.enqueue_monitor_snapshot_refresh
        self.original_fallback = monitor_snapshot_service.fallback_watchlist_signals
        self.enqueued: list[tuple[int, int]] = []
        monitor_snapshot_service.list_user_watchlist_rows = lambda db, user_id: [object()]  # noqa: ARG005
        monitor_snapshot_service.rows_signature = lambda rows: [["510300"]]  # noqa: ARG005
        monitor_snapshot_service.enqueue_monitor_snapshot_refresh = self._enqueue_stub
        monitor_snapshot_service.fallback_watchlist_signals = lambda rows, reason: [  # noqa: ARG005
            {"symbol": "510300", "name": "沪深300ETF", "error": reason}
        ]
        app = FastAPI()
        app.include_router(monitor.router, prefix="/api")
        app.dependency_overrides[get_current_user] = _override_user
        app.dependency_overrides[get_db] = _override_db
        self.client = TestClient(app)

    def tearDown(self) -> None:
        monitor_snapshot_service.list_user_watchlist_rows = self.original_list_rows
        monitor_snapshot_service.rows_signature = self.original_signature
        monitor_snapshot_service.read_monitor_snapshot_cache = self.original_read_cache
        monitor_snapshot_service.enqueue_monitor_snapshot_refresh = self.original_enqueue
        monitor_snapshot_service.fallback_watchlist_signals = self.original_fallback

    def _enqueue_stub(self, db, *, user_id: int, priority_limit: int) -> None:  # noqa: ANN001, ARG002
        self.enqueued.append((user_id, priority_limit))

    def test_monitor_snapshot_returns_cached_board_without_web_refresh(self) -> None:
        monitor_snapshot_service.read_monitor_snapshot_cache = lambda db, **kwargs: MonitorSnapshotCacheHit(  # noqa: ARG005
            payload={
                "updated_at": "2026-05-02 10:00:00",
                "watchlist_signals": [{"symbol": "510300", "name": "沪深300ETF"}],
                "priority_board": {"updated_at": "2026-05-02 10:00:00", "total_candidates": 1, "items": []},
            },
            needs_refresh=False,
        )
        response = self.client.get("/api/monitor/snapshot?priority_limit=12")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["watchlist_signals"][0]["symbol"], "510300")
        self.assertEqual(payload["priority_board"]["total_candidates"], 1)
        self.assertEqual(self.enqueued, [])

    def test_monitor_snapshot_cold_start_enqueues_runtime_task(self) -> None:
        monitor_snapshot_service.read_monitor_snapshot_cache = lambda db, **kwargs: None  # noqa: ARG005
        response = self.client.get("/api/monitor/snapshot?priority_limit=12")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["watchlist_signals"][0]["symbol"], "510300")
        self.assertEqual(payload["priority_board"]["total_candidates"], 0)
        self.assertEqual(self.enqueued, [(1, 12)])


if __name__ == "__main__":
    unittest.main()
