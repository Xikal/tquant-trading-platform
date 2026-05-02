from __future__ import annotations

import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.entities import Watchlist
from app.services.watchlist_signal_service import WatchlistSignalService


class _NonBlockingWatchlistSignalService(WatchlistSignalService):
    def __init__(self) -> None:
        self.background_refresh_requests: list[bool] = []

    def ensure_background_refresh(self, force: bool = False) -> bool:
        self.background_refresh_requests.append(force)
        return True

    def refresh_snapshots(self, force: bool = False) -> None:  # noqa: ARG002
        raise AssertionError("list_signals must not block on synchronous refresh")


class WatchlistSignalServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine, future=True)

    def test_list_signals_returns_pending_payload_without_blocking_refresh(self) -> None:
        service = _NonBlockingWatchlistSignalService()
        with self.Session() as db:
            db.add(
                Watchlist(
                    symbol="510300",
                    name="沪深300ETF",
                    base_position=3000,
                    available_position=3000,
                    cost_basis=4.02,
                )
            )
            db.commit()

            payloads = service.list_signals(db)

        self.assertEqual(len(payloads), 1)
        self.assertEqual(payloads[0]["symbol"], "510300")
        self.assertEqual(payloads[0]["name"], "沪深300ETF")
        self.assertEqual(payloads[0]["error"], "监控信号缓存仍在准备中。")
        self.assertIn(True, service.background_refresh_requests)


if __name__ == "__main__":
    unittest.main()
