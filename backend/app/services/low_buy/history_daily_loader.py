from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, wait
from datetime import datetime, timedelta
import logging

from app.repositories.low_buy import DailyHistoryRepository
from app.services.low_buy.history_cache_mixin import LowBuyHistoryCacheMixin
from app.services.low_buy.history_frames import (
    build_intraday_history_frame,
    finalize_daily_history_frame,
    frame_to_daily_bar_rows,
    rows_to_daily_history_frame,
)
from app.services.low_buy.shared import BoardCandidate, Session, SessionLocal, pd

logger = logging.getLogger(__name__)


class LowBuyDailyHistoryMixin(LowBuyHistoryCacheMixin):
    def _load_daily_history(self, symbol: str, latest_trade_date: str, history_window_days: int = 180) -> pd.DataFrame | None:
        cache_key = f"{symbol}:{latest_trade_date}:{history_window_days}"
        cached = self._get_daily_history_cache(cache_key)
        if cached is not None:
            return cached.copy(deep=True) if cached is not None else None

        start_date = datetime.strptime(latest_trade_date, "%Y-%m-%d") - timedelta(days=history_window_days)
        start_date_iso = start_date.date().isoformat()
        with SessionLocal() as db:
            normalized = self._load_daily_history_from_db(
                db=db,
                symbol=symbol,
                start_date_iso=start_date_iso,
                latest_trade_date=latest_trade_date,
            )
            latest_local_date = str(normalized["date"].iloc[-1]) if normalized is not None and not normalized.empty else None
            needs_sync = normalized is None or normalized.empty or len(normalized) < 60 or latest_local_date != latest_trade_date
            if needs_sync:
                sync_start_iso = start_date_iso
                if latest_local_date and normalized is not None and not normalized.empty and len(normalized) >= 60:
                    overlap_start = datetime.strptime(latest_local_date, "%Y-%m-%d") - timedelta(days=7)
                    sync_start_iso = max(start_date_iso, overlap_start.date().isoformat())
                remote_history = self._fetch_remote_daily_history(
                    symbol=symbol,
                    start_date_iso=sync_start_iso,
                    latest_trade_date=latest_trade_date,
                )
                if remote_history is not None and not remote_history.empty:
                    self._persist_daily_history_rows(db=db, symbol=symbol, history=remote_history)
                    normalized = self._load_daily_history_from_db(
                        db=db,
                        symbol=symbol,
                        start_date_iso=start_date_iso,
                        latest_trade_date=latest_trade_date,
                    )

        if normalized is None or normalized.empty:
            return None
        self._set_daily_history_cache(cache_key, normalized)
        return normalized.copy(deep=True)

    def _load_daily_history_from_db(self, db: Session, symbol: str, start_date_iso: str, latest_trade_date: str) -> pd.DataFrame | None:
        rows = DailyHistoryRepository(db).fetch_rows(
            symbol=symbol,
            start_date_iso=start_date_iso,
            latest_trade_date=latest_trade_date,
        )
        if not rows:
            return None
        return rows_to_daily_history_frame(rows, start_date_iso)

    def _fetch_remote_daily_history(self, symbol: str, start_date_iso: str, latest_trade_date: str) -> pd.DataFrame | None:
        start_date_str = start_date_iso.replace("-", "")
        end_date_str = latest_trade_date.replace("-", "")
        routed = self.market_data.provider_router.fetch_daily_history(symbol, start_date_str, end_date_str)
        normalized = routed.data if routed.usable else None
        if normalized is None or normalized.empty:
            return None
        return finalize_daily_history_frame(normalized, start_date_iso)

    def _build_intraday_history(self, history: pd.DataFrame | None, active_trade_date: str, quote) -> pd.DataFrame | None:
        return build_intraday_history_frame(history, active_trade_date=active_trade_date, quote=quote)

    def _persist_daily_history_rows(self, db: Session, symbol: str, history: pd.DataFrame) -> None:
        if history.empty:
            return
        rows = frame_to_daily_bar_rows(history)
        DailyHistoryRepository(db).upsert_rows(symbol=symbol, payloads=rows)
        db.commit()

    def _finalize_daily_history_frame(self, normalized: pd.DataFrame | None, start_date_iso: str) -> pd.DataFrame | None:
        return finalize_daily_history_frame(normalized, start_date_iso)

    def _load_histories(
        self,
        items: list[BoardCandidate],
        latest_trade_date: str,
        active_trade_date: str | None = None,
        quote_map: dict[str, object] | None = None,
        wait_timeout_seconds: float | None = None,
    ) -> dict[str, pd.DataFrame | None]:
        if not items:
            return {}
        results: dict[str, pd.DataFrame | None] = {}
        max_workers = min(8 if len(items) > 120 else 6, len(items))
        history_wait_timeout = (
            max(float(wait_timeout_seconds), 1.0)
            if wait_timeout_seconds is not None
            else max(float(self.market_data.settings.akshare_timeout_seconds or 12), 12.0) * 2.0
        )
        executor = ThreadPoolExecutor(max_workers=max_workers)
        try:
            future_map = {executor.submit(self._load_daily_history, item.symbol, latest_trade_date): item.symbol for item in items}
            done, not_done = wait(future_map, timeout=history_wait_timeout)
            for future in done:
                symbol = future_map[future]
                try:
                    results[symbol] = future.result()
                except Exception:
                    results[symbol] = None
            if not_done:
                logger.warning(
                    "low-buy history load timed out after %.1fs for %d/%d symbols",
                    history_wait_timeout,
                    len(not_done),
                    len(items),
                )
                for future in not_done:
                    symbol = future_map[future]
                    results[symbol] = None
                    future.cancel()
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
        if active_trade_date and active_trade_date > latest_trade_date:
            for item in items:
                results[item.symbol] = self._build_intraday_history(
                    results.get(item.symbol),
                    active_trade_date=active_trade_date,
                    quote=quote_map.get(item.symbol) if quote_map else None,
                )
        return results
