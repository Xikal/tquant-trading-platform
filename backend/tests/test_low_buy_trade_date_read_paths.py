from __future__ import annotations

import unittest

from app.services.low_buy import pool as pool_module
from app.services.low_buy import pool_trade_dates as trade_date_module
from app.services.low_buy.pool import LowBuyPoolMixin


class _TradeDateService(LowBuyPoolMixin):
    def __init__(self, latest_artifact_trade_date: str | None, complete_dates: set[str] | None = None) -> None:
        self.latest_artifact_trade_date = latest_artifact_trade_date
        self.complete_dates = complete_dates or set()

    def _load_latest_low_buy_artifact_trade_date(self, trade_dates: list[str]) -> str | None:
        if self.latest_artifact_trade_date in trade_dates:
            return self.latest_artifact_trade_date
        return None

    def _load_daily_history(self, symbol: str, latest_trade_date: str, history_window_days: int = 180):  # noqa: ARG002
        return None

    def _has_complete_local_daily_bars(self, trade_date: str, min_stock_count: int = 4500) -> bool:  # noqa: ARG002
        return trade_date in self.complete_dates


class LowBuyTradeDateReadPathTests(unittest.TestCase):
    def test_resolve_latest_completed_trade_date_uses_low_buy_artifact_when_daily_history_lags(self) -> None:
        service = _TradeDateService(
            latest_artifact_trade_date="2026-04-24",
            complete_dates={"2026-04-24"},
        )

        self.assertEqual(
            service._resolve_latest_completed_trade_date(["2026-04-22", "2026-04-23", "2026-04-24"]),
            "2026-04-24",
        )

    def test_resolve_latest_completed_trade_date_rejects_incomplete_artifact(self) -> None:
        service = _TradeDateService(latest_artifact_trade_date="2026-04-30")
        original_session = pool_module.SessionLocal
        original_repository = pool_module.DailyHistoryRepository

        class _FakeSession:
            def __enter__(self):
                return object()

            def __exit__(self, exc_type, exc, tb):
                return False

        class _FakeRepository:
            def __init__(self, db):  # noqa: ARG002
                pass

            @staticmethod
            def latest_complete_trade_date(max_trade_date: str, min_stock_count: int):  # noqa: ARG002
                return None

            @staticmethod
            def latest_trade_date_for_symbol(symbol: str):  # noqa: ARG002
                return "2026-04-30"

            @staticmethod
            def stock_count_by_trade_date(trade_date: str) -> int:
                return {"2026-04-28": 5177, "2026-04-29": 507, "2026-04-30": 405}.get(trade_date, 0)

        try:
            pool_module.SessionLocal = _FakeSession
            pool_module.DailyHistoryRepository = _FakeRepository
            self.assertEqual(
                service._resolve_latest_completed_trade_date(["2026-04-28", "2026-04-29", "2026-04-30"]),
                "2026-04-28",
            )
        finally:
            pool_module.SessionLocal = original_session
            pool_module.DailyHistoryRepository = original_repository

    def test_latest_completed_calendar_fallback_uses_latest_completed_holiday_date(self) -> None:
        service = _TradeDateService(latest_artifact_trade_date=None)
        original_date = pool_module.date

        class _FakeDate:
            @classmethod
            def today(cls):
                return original_date(2026, 5, 4)

        try:
            pool_module.date = _FakeDate
            self.assertEqual(
                service._latest_completed_calendar_fallback(["2026-04-28", "2026-04-29", "2026-04-30"]),
                "2026-04-30",
            )
            self.assertEqual(
                service._latest_completed_calendar_fallback(["2026-04-30", "2026-05-04"]),
                "2026-04-30",
            )
        finally:
            pool_module.date = original_date

    def test_recent_trade_dates_do_not_call_remote_calendar_when_local_store_lags(self) -> None:
        service = _TradeDateService(latest_artifact_trade_date=None)
        service._trade_dates_cache = {}
        original_date = pool_module.date
        remote_called = False

        class _FakeDate:
            @classmethod
            def today(cls):
                return original_date(2026, 5, 4)

        try:
            pool_module.date = _FakeDate
            service._load_recent_trade_dates_from_local_store = lambda count: ["2026-04-28", "2026-04-29"]  # type: ignore[method-assign]

            def _remote_calendar(*, count, today):  # noqa: ANN001
                nonlocal remote_called
                remote_called = True
                return ["2026-04-30"]

            service._load_recent_trade_dates_from_remote = _remote_calendar  # type: ignore[method-assign]

            self.assertEqual(
                service._get_recent_trade_dates(14),
                ["2026-04-28", "2026-04-29"],
            )
            self.assertFalse(remote_called)
        finally:
            pool_module.date = original_date

    def test_recent_trade_dates_append_today_from_local_calendar_for_intraday_mode(self) -> None:
        service = _TradeDateService(latest_artifact_trade_date=None)
        service._trade_dates_cache = {}
        original_date = pool_module.date

        class _FakeDate:
            @classmethod
            def today(cls):
                return original_date(2026, 4, 30)

        try:
            pool_module.date = _FakeDate
            service._load_recent_trade_dates_from_local_store = lambda count: ["2026-04-28", "2026-04-29"]  # type: ignore[method-assign]
            service._load_recent_trade_dates_from_remote = lambda *, count, today: (_ for _ in ()).throw(  # type: ignore[method-assign]
                AssertionError("remote calendar must not be called from read path")
            )

            self.assertEqual(
                service._get_recent_trade_dates(14),
                ["2026-04-28", "2026-04-29", "2026-04-30"],
            )
        finally:
            pool_module.date = original_date

    def test_recent_trade_dates_fallback_to_materialized_low_buy_dates_when_daily_store_is_empty(self) -> None:
        service = _TradeDateService(latest_artifact_trade_date=None)
        service._trade_dates_cache = {}
        original_date = pool_module.date
        original_session = pool_module.SessionLocal
        original_daily_repository = pool_module.DailyHistoryRepository
        original_result_repository = trade_date_module.LowBuyResultRepository

        class _FakeDate:
            @classmethod
            def today(cls):
                return original_date(2026, 6, 9)

        class _FakeSession:
            def __enter__(self):
                return object()

            def __exit__(self, exc_type, exc, tb):
                return False

        class _FakeDailyRepository:
            def __init__(self, db):  # noqa: ARG002
                pass

            @staticmethod
            def fetch_recent_trade_dates(count: int):  # noqa: ARG002
                return []

        class _FakeResultRepository:
            def __init__(self, db):  # noqa: ARG002
                pass

            @staticmethod
            def fetch_recent_trade_dates(limit: int = 14):  # noqa: ARG002
                return ["2026-06-05", "2026-06-08", "2026-06-09"]

            @staticmethod
            def fetch_latest_trade_date(strategy_key=None):  # noqa: ARG002
                return "2026-06-09"

        try:
            pool_module.date = _FakeDate
            pool_module.SessionLocal = _FakeSession
            pool_module.DailyHistoryRepository = _FakeDailyRepository
            trade_date_module.LowBuyResultRepository = _FakeResultRepository

            self.assertEqual(
                service._get_recent_trade_dates(14),
                ["2026-06-05", "2026-06-08", "2026-06-09"],
            )
        finally:
            pool_module.date = original_date
            pool_module.SessionLocal = original_session
            pool_module.DailyHistoryRepository = original_daily_repository
            trade_date_module.LowBuyResultRepository = original_result_repository


if __name__ == "__main__":
    unittest.main()
