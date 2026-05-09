from __future__ import annotations

from datetime import date
import sys
import time

from app.repositories.low_buy import DailyHistoryRepository, LowBuyResultRepository
from app.services.low_buy.shared import (
    INTRADAY_STRUCTURE_START_HOUR,
    INTRADAY_STRUCTURE_START_MINUTE,
    SessionLocal,
)
from app.services.market.trading_calendar import is_a_share_trading_day
from app.core.timezone import beijing_now


class LowBuyTradeDateMixin:
    def _resolve_active_structure_trade_date(
        self,
        trade_dates: list[str],
        latest_completed_trade_date: str,
    ) -> str:
        if not trade_dates:
            return latest_completed_trade_date
        today = _date_cls().today().isoformat()
        if today <= latest_completed_trade_date or today not in trade_dates:
            return latest_completed_trade_date
        now = beijing_now()
        after_structure_open = (now.hour, now.minute) >= (
            INTRADAY_STRUCTURE_START_HOUR,
            INTRADAY_STRUCTURE_START_MINUTE,
        )
        during_session = (now.hour, now.minute) >= (9, 30) and (now.hour, now.minute) <= (15, 10)
        return today if after_structure_open and during_session else latest_completed_trade_date

    def _resolve_latest_completed_trade_date(self, trade_dates: list[str]) -> str:
        latest_completed_fallback = self._latest_completed_calendar_fallback(trade_dates)
        try:
            with _session_factory()() as db:
                repository = _daily_history_repository()(db)
                latest_complete_trade_date = repository.latest_complete_trade_date(
                    max_trade_date=trade_dates[-1],
                    min_stock_count=4500,
                )
                latest_stored_trade_date = repository.latest_trade_date_for_symbol("000001")
                latest_stored_count = (
                    repository.stock_count_by_trade_date(latest_stored_trade_date)
                    if latest_stored_trade_date
                    else 0
                )
        except Exception:
            latest_complete_trade_date = None
            latest_stored_trade_date = None
            latest_stored_count = 0
        if latest_complete_trade_date and latest_complete_trade_date >= latest_completed_fallback:
            return str(latest_complete_trade_date)
        if (
            latest_stored_trade_date
            and latest_stored_trade_date >= latest_completed_fallback
            and latest_stored_count >= 4500
        ):
            return str(latest_stored_trade_date)
        latest_artifact_trade_date = self._load_latest_low_buy_artifact_trade_date(trade_dates)
        if (
            latest_artifact_trade_date
            and latest_artifact_trade_date >= latest_completed_fallback
            and self._has_complete_local_daily_bars(latest_artifact_trade_date)
        ):
            return latest_artifact_trade_date

        probe = self._load_daily_history("000001", trade_dates[-1], history_window_days=20)
        if probe is not None and not probe.empty:
            probe_trade_date = str(probe["date"].iloc[-1])
            if self._has_complete_local_daily_bars(probe_trade_date):
                return probe_trade_date

        try:
            with _session_factory()() as db:
                repo = _daily_history_repository()(db)
                for candidate_date in reversed(trade_dates[:-1]):
                    if repo.stock_count_by_trade_date(candidate_date) >= 4500:
                        return candidate_date
        except Exception:
            pass
        return latest_completed_fallback

    @staticmethod
    def _latest_completed_calendar_fallback(trade_dates: list[str]) -> str:
        if not trade_dates:
            return ""
        today = _date_cls().today().isoformat()
        latest_calendar_date = trade_dates[-1]
        if latest_calendar_date < today or len(trade_dates) == 1:
            return latest_calendar_date
        return trade_dates[-2]

    @staticmethod
    def _has_complete_local_daily_bars(trade_date: str, min_stock_count: int = 4500) -> bool:
        try:
            with _session_factory()() as db:
                return _daily_history_repository()(db).stock_count_by_trade_date(trade_date) >= min_stock_count
        except Exception:
            return False

    def _load_latest_low_buy_artifact_trade_date(self, trade_dates: list[str]) -> str | None:
        if not trade_dates:
            return None
        try:
            with _session_factory()() as db:
                latest_trade_date = LowBuyResultRepository(db).fetch_latest_trade_date()
        except Exception:
            return None
        if latest_trade_date is None:
            return None
        normalized = str(latest_trade_date)
        return normalized if normalized in trade_dates else None

    def _get_recent_trade_dates(self, count: int) -> list[str]:
        cache_key = f"recent-trade-dates:{count}:{_date_cls().today().isoformat()}"
        cached = getattr(self, "_trade_dates_cache", {}).get(cache_key)
        now = time.monotonic()
        if cached and cached[0] > now:
            return list(cached[1])

        local_values = self._load_recent_trade_dates_from_local_store(count)
        trade_dates = self._with_intraday_trade_date(local_values, count=count)
        return self._cache_recent_trade_dates(cache_key, trade_dates)

    @staticmethod
    def _with_intraday_trade_date(local_values: list[str], *, count: int) -> list[str]:
        today_value = _date_cls().today()
        today = today_value.isoformat()
        values = [item for item in local_values if item <= today]
        if is_a_share_trading_day(today_value) and today not in values:
            values.append(today)
        return sorted(set(values))[-count:]

    def _load_recent_trade_dates_from_remote(self, *, count: int, today: str) -> list[str]:
        routed = self.market_data.provider_router.fetch_trade_dates()
        if not routed.usable or routed.data is None:
            return []
        values = [item.isoformat() if hasattr(item, "isoformat") else str(item) for item in routed.data["trade_date"].tolist()]
        return [item for item in values if item <= today][-count:]

    def _load_recent_trade_dates_from_local_store(self, count: int) -> list[str]:
        try:
            with _session_factory()() as db:
                values = _daily_history_repository()(db).fetch_recent_trade_dates(count)
        except Exception:
            return []
        today = _date_cls().today().isoformat()
        return [item for item in values if item <= today][-count:]

    def _cache_recent_trade_dates(self, cache_key: str, values: list[str]) -> list[str]:
        cache = getattr(self, "_trade_dates_cache", None)
        if cache is None:
            cache = {}
            setattr(self, "_trade_dates_cache", cache)
        ttl = float(getattr(self, "_trade_dates_cache_ttl", 3600.0))
        cache[cache_key] = (time.monotonic() + ttl, list(values))
        return list(values)


def _pool_module_attr(name: str, fallback):
    pool_module = sys.modules.get("app.services.low_buy.pool")
    return getattr(pool_module, name, fallback) if pool_module is not None else fallback


def _date_cls():
    return _pool_module_attr("date", date)


def _session_factory():
    return _pool_module_attr("SessionLocal", SessionLocal)


def _daily_history_repository():
    return _pool_module_attr("DailyHistoryRepository", DailyHistoryRepository)
