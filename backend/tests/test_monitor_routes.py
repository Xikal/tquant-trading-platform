from __future__ import annotations

import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import monitor
from app.core.auth import get_current_user
from app.core.database import get_db


class _BoardStub:
    def model_dump(self):
        return {
            "updated_at": "2026-05-02 10:00:00",
            "total_candidates": 1,
            "items": [{"symbol": "510300"}],
        }


class _LowBuyStub:
    def priority_board(self, db, limit=24):  # noqa: ANN001, ARG002
        self.limit = limit
        return _BoardStub()


class _WatchlistStub:
    def build_live_signals(self, db, rows):  # noqa: ANN001, ARG002
        return [{"symbol": "510300", "name": "沪深300ETF"}]


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
        self.original_low_buy = monitor.low_buy_screener
        self.original_watchlist = monitor.watchlist_signal_service
        self.original_list_rows = monitor._list_user_watchlist_rows
        monitor.low_buy_screener = _LowBuyStub()
        monitor.watchlist_signal_service = _WatchlistStub()
        monitor._list_user_watchlist_rows = lambda db, user_id: [object()]  # noqa: ARG005
        app = FastAPI()
        app.include_router(monitor.router, prefix="/api")
        app.dependency_overrides[get_current_user] = _override_user
        app.dependency_overrides[get_db] = _override_db
        self.client = TestClient(app)

    def tearDown(self) -> None:
        monitor.low_buy_screener = self.original_low_buy
        monitor.watchlist_signal_service = self.original_watchlist
        monitor._list_user_watchlist_rows = self.original_list_rows

    def test_monitor_snapshot_returns_board_and_watchlist_once(self) -> None:
        response = self.client.get("/api/monitor/snapshot?priority_limit=12")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["watchlist_signals"][0]["symbol"], "510300")
        self.assertEqual(payload["priority_board"]["total_candidates"], 1)


if __name__ == "__main__":
    unittest.main()
