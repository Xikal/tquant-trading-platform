from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed
import logging

from app.services.market.shared import DataSourceError, QuoteSnapshot

logger = logging.getLogger(__name__)


class QuoteSourceRouter:
    def __init__(self, service) -> None:
        self.service = service

    def fetch(self, symbol: str) -> QuoteSnapshot:
        stale_candidate: QuoteSnapshot | None = None
        try:
            snapshot = self.service._fetch_tencent_quote(symbol)
            if snapshot is not None and not getattr(snapshot, "is_stale", False):
                return snapshot
            stale_candidate = snapshot
        except Exception as exc:
            logger.debug("primary quote source failed for %s: %s", symbol, exc)

        try:
            snapshot = self.service._fetch_eastmoney_realtime_quote(symbol)
            if snapshot is not None and not getattr(snapshot, "is_stale", False):
                return snapshot
            stale_candidate = stale_candidate or snapshot
        except Exception as exc:
            logger.debug("eastmoney quote source failed for %s: %s", symbol, exc)

        alternatives = (
            self.service._fetch_quote_from_trends,
            self.service._fetch_quote_from_minute_bars,
            self.service._fetch_quote_from_spot_snapshot,
        )
        with ThreadPoolExecutor(max_workers=3, thread_name_prefix="quote-fallback") as pool:
            futures = {pool.submit(loader, symbol): loader for loader in alternatives}
            try:
                for future in as_completed(futures, timeout=3.0):
                    try:
                        snapshot = future.result()
                    except Exception:
                        continue
                    if snapshot is not None:
                        for pending in futures:
                            pending.cancel()
                        return snapshot
            except TimeoutError:
                for pending in futures:
                    pending.cancel()

        try:
            return self.service._fetch_sina_quote(symbol)
        except Exception as exc:
            if stale_candidate is not None:
                return stale_candidate
            raise DataSourceError(f"未获取到 {symbol} 的实时行情。") from exc

    def fetch_batch(self, symbols: list[str], allow_slow_fallback: bool = True) -> dict[str, QuoteSnapshot]:
        result: dict[str, QuoteSnapshot] = {}
        remaining = list(symbols)
        stale_candidates: dict[str, QuoteSnapshot] = {}
        try:
            batch_quotes = self.service._fetch_tencent_quotes_batch(remaining)
        except Exception:
            batch_quotes = {}
        for symbol, snapshot in batch_quotes.items():
            if getattr(snapshot, "is_stale", False):
                stale_candidates[symbol] = snapshot
            else:
                result[symbol] = snapshot
        if not allow_slow_fallback:
            return result or stale_candidates
        remaining = [symbol for symbol in remaining if symbol not in result]
        if remaining:
            try:
                eastmoney_quotes = self.service._fetch_eastmoney_realtime_quotes_batch(remaining)
            except Exception:
                eastmoney_quotes = {}
            for symbol, snapshot in eastmoney_quotes.items():
                if getattr(snapshot, "is_stale", False):
                    stale_candidates.setdefault(symbol, snapshot)
                else:
                    result[symbol] = snapshot
        remaining = [symbol for symbol in remaining if symbol not in result]
        if remaining:
            grouped = self._group_remaining_by_instrument_type(remaining)
            for instrument_type, grouped_symbols in grouped.items():
                try:
                    snapshot_map = self.service._load_spot_snapshot_map(instrument_type)
                except Exception:
                    continue
                for symbol in grouped_symbols:
                    snapshot = snapshot_map.get(symbol)
                    if snapshot is not None:
                        result[symbol] = snapshot
        remaining = [symbol for symbol in remaining if symbol not in result]
        for symbol in remaining:
            try:
                result[symbol] = self.fetch(symbol)
            except Exception:
                continue
        for symbol, snapshot in stale_candidates.items():
            result.setdefault(symbol, snapshot)
        return result

    def _group_remaining_by_instrument_type(self, symbols: list[str]) -> dict[str, list[str]]:
        grouped: dict[str, list[str]] = {"stock": [], "etf": []}
        for symbol in symbols:
            instrument_type = (
                "etf"
                if __import__("app.services.market.shared", fromlist=["MarketRuleService"]).MarketRuleService.looks_like_etf(symbol)
                else "stock"
            )
            grouped[instrument_type].append(symbol)
        return {key: value for key, value in grouped.items() if value}
