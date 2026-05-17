from __future__ import annotations

from copy import deepcopy
import logging
import time

from app.models.schemas import LowBuyCandidateOut, LowBuyQuoteRefreshOut, LowBuyScreenerResponse
from app.services.low_buy.price_math import distance_to_entry_zone_pct
from app.repositories.low_buy.results import LowBuyResultRepository
from app.services.low_buy.shared import LOW_BUY_THRESHOLDS, Session
from app.services.low_buy.data_quality import build_candidate_data_quality, data_quality_payload

logger = logging.getLogger(__name__)

MAX_QUOTE_REFRESH_SYMBOLS = LOW_BUY_THRESHOLDS.MAX_SYMBOLS_QUOTE_REFRESH


class LowBuyQuoteRefreshMixin:
    def refresh_candidate_quotes(
        self,
        db: Session,
        strategy: str,
        symbols: list[str],
    ) -> dict[str, LowBuyQuoteRefreshOut]:
        symbols = self._normalize_quote_refresh_symbols(symbols)
        if not symbols:
            return {}

        latest_trade_date = self._resolve_quote_refresh_trade_date(db, strategy)
        materialized = self._load_materialized_candidates_by_symbol(
            db=db,
            strategy=strategy,
            latest_trade_date=latest_trade_date,
            symbols=symbols,
        )
        if len(materialized) < len(symbols):
            materialized = {
                **self._load_cached_candidates_by_symbol(
                    strategy=strategy,
                    latest_trade_date=latest_trade_date,
                    symbols=symbols,
                ),
                **materialized,
            }
        return self._build_quote_refresh_payloads(symbols, materialized)

    @staticmethod
    def _normalize_quote_refresh_symbols(symbols: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for symbol in symbols:
            cleaned = str(symbol).strip().upper()
            if not cleaned or cleaned in seen:
                continue
            seen.add(cleaned)
            normalized.append(cleaned)
            if len(normalized) >= MAX_QUOTE_REFRESH_SYMBOLS:
                break
        return normalized

    def _resolve_quote_refresh_trade_date(self, db: Session, strategy: str) -> str:
        summary = LowBuyResultRepository(db).fetch_latest_scan_summary(strategy)
        if summary is not None and self._materialized_scan_is_current(
            db=db,
            strategy=strategy,
            latest_trade_date=str(summary.latest_trade_date),
            summary=summary,
        ):
            return str(summary.latest_trade_date)
        trade_dates = self._get_recent_trade_dates(14)
        latest_completed_trade_date = self._resolve_latest_completed_trade_date(trade_dates)
        return self._resolve_active_structure_trade_date(
            trade_dates=trade_dates,
            latest_completed_trade_date=latest_completed_trade_date,
        )

    def _build_quote_refresh_payloads(
        self,
        symbols: list[str],
        materialized: dict[str, LowBuyCandidateOut],
    ) -> dict[str, LowBuyQuoteRefreshOut]:
        refreshed: dict[str, LowBuyQuoteRefreshOut] = {}
        deduped_symbols = list(dict.fromkeys(symbols))
        cache_key = self._quote_refresh_cache_key(deduped_symbols, materialized)
        cached = self._get_quote_refresh_response_cache(cache_key)
        if cached is not None:
            return cached

        try:
            batch_quotes = self.market_data.get_quotes_batch(
                deduped_symbols,
                force_refresh=True,
                allow_slow_fallback=False,
            )
        except Exception as exc:
            logger.warning("low-buy quote refresh skipped: quote source failed: %s", exc)
            return {}
        intraday_bars_by_symbol = self._load_quote_refresh_intraday_bars_batch(
            symbols=deduped_symbols,
            materialized=materialized,
            quote_map=batch_quotes,
        )
        for symbol in deduped_symbols:
            quote = batch_quotes.get(symbol)
            if quote is None:
                continue
            candidate = materialized.get(symbol)
            if candidate is None:
                refreshed[symbol] = self._quote_refresh_without_context(quote)
                continue
            try:
                refreshed[symbol] = self._quote_refresh_with_context(
                    candidate,
                    quote,
                    intraday_bars=intraday_bars_by_symbol.get(symbol),
                )
            except Exception as exc:
                logger.warning("low-buy quote refresh degraded for %s: %s", symbol, exc)
                refreshed[symbol] = self._quote_refresh_without_context(quote)
        self._set_quote_refresh_response_cache(cache_key, refreshed)
        return refreshed

    @staticmethod
    def _quote_refresh_cache_key(
        symbols: list[str],
        materialized: dict[str, LowBuyCandidateOut],
    ) -> str:
        context_versions = []
        for symbol in symbols:
            candidate = materialized.get(symbol)
            if candidate is None:
                context_versions.append(f"{symbol}:none")
                continue
            context_versions.append(
                f"{symbol}:{candidate.strategy_key}:{candidate.quote_timestamp}:{candidate.buy_signal_state}"
            )
        return "|".join(context_versions)

    def _get_quote_refresh_response_cache(
        self,
        cache_key: str,
    ) -> dict[str, LowBuyQuoteRefreshOut] | None:
        now = time.monotonic()
        with self._cache_lock:
            cached = self._quote_refresh_response_cache.get(cache_key)
            if cached is None:
                return None
            expires_at, payload = cached
            if expires_at <= now:
                self._quote_refresh_response_cache.pop(cache_key, None)
                return None
            return deepcopy(payload)

    def _set_quote_refresh_response_cache(
        self,
        cache_key: str,
        payload: dict[str, LowBuyQuoteRefreshOut],
    ) -> None:
        with self._cache_lock:
            self._quote_refresh_response_cache[cache_key] = (
                time.monotonic() + self._quote_refresh_response_cache_ttl,
                deepcopy(payload),
            )

    @staticmethod
    def _quote_refresh_without_context(quote) -> LowBuyQuoteRefreshOut:
        quote_meta = LowBuyQuoteRefreshMixin._quote_metadata(quote)
        quality_fields = data_quality_payload(
            build_candidate_data_quality(
                latest_price=float(quote.last_price),
                quote_timestamp=str(quote.timestamp),
                source_quality=str(quote_meta.get("source_quality") or ""),
                is_stale=bool(quote_meta.get("is_stale", False)),
                change_pct=float(quote.change_pct),
            )
        )
        return LowBuyQuoteRefreshOut(
            latest_price=round(float(quote.last_price), 3),
            change_pct=round(float(quote.change_pct), 3),
            quote_timestamp=str(quote.timestamp),
            **quote_meta,
            **quality_fields,
            in_entry_zone=False,
            distance_to_entry_pct=0.0,
            stop_confirmed=False,
            suggested_position_pct=0.0,
            suggested_position_text="等待当前策略上下文。",
            position_breakdown_text="",
            execution_quality_score=0.0,
            execution_quality_text="执行质量：缺少策略上下文，不能判断。",
            buy_signal_state="watch",
            buy_signal_text="继续观察",
            buy_signal_hint="当前只更新了最新价格，这只票暂时不在本策略结果里。",
            trigger_condition="先加载对应策略结果，再判断是否进入买点。",
            invalid_condition="没有策略上下文时，不给买入结论。",
            risk_tier="note",
            next_watch_price=None,
        )

    def _quote_refresh_with_context(
        self,
        candidate: LowBuyCandidateOut,
        quote,
        intraday_bars=None,
    ) -> LowBuyQuoteRefreshOut:
        updated_candidate = candidate.model_copy(
            update={
                "latest_price": round(float(quote.last_price), 3),
                "change_pct": round(float(quote.change_pct), 3),
                "quote_timestamp": str(quote.timestamp),
            }
        )
        signal = self._refresh_buy_signal(
            updated_candidate,
            quote=quote,
            intraday_bars=intraday_bars,
            require_intraday_structure=True,
        )
        quote_meta = self._quote_metadata(quote)
        quality_fields = data_quality_payload(
            build_candidate_data_quality(
                latest_price=float(quote.last_price),
                quote_timestamp=str(quote.timestamp),
                source_quality=str(quote_meta.get("source_quality") or ""),
                is_stale=bool(quote_meta.get("is_stale", False)),
                change_pct=float(quote.change_pct),
            )
        )
        return LowBuyQuoteRefreshOut(
            latest_price=round(float(quote.last_price), 3),
            change_pct=round(float(quote.change_pct), 3),
            quote_timestamp=str(quote.timestamp),
            **quote_meta,
            **quality_fields,
            in_entry_zone=self._is_in_entry_zone(signal),
            distance_to_entry_pct=distance_to_entry_zone_pct(signal, quote.last_price),
            stop_confirmed=self._is_intraday_stop_confirmed(
                signal,
                quote,
                intraday_bars=intraday_bars,
                require_intraday_structure=True,
            ),
            suggested_position_pct=signal.suggested_position_pct,
            suggested_position_text=signal.suggested_position_text,
            position_breakdown_text=signal.position_breakdown_text,
            execution_quality_score=signal.execution_quality_score,
            execution_quality_text=signal.execution_quality_text,
            buy_signal_state=signal.buy_signal_state,
            buy_signal_text=signal.buy_signal_text,
            buy_signal_hint=signal.buy_signal_hint,
            trigger_condition=signal.trigger_condition,
            invalid_condition=signal.invalid_condition,
            risk_tier=signal.risk_tier,
            next_watch_price=signal.next_watch_price,
            atr_pct=signal.atr_pct,
            atr_window=signal.atr_window,
            atr_source=signal.atr_source,
        )

    @staticmethod
    def _quote_metadata(quote) -> dict[str, object]:
        return {
            "data_source": getattr(quote, "data_source", None),
            "source_quality": getattr(quote, "source_quality", None),
            "is_stale": bool(getattr(quote, "is_stale", False)),
        }

    def _load_quote_refresh_intraday_bars_batch(
        self,
        *,
        symbols: list[str],
        materialized: dict[str, LowBuyCandidateOut],
        quote_map: dict[str, object],
        max_symbols: int = LOW_BUY_THRESHOLDS.MAX_SYMBOLS_QUOTE_REFRESH,
    ) -> dict[str, list]:
        selected_symbols = self._select_intraday_refresh_symbols(
            symbols=symbols,
            materialized=materialized,
            quote_map=quote_map,
            max_symbols=max_symbols,
        )
        return self.market_data.get_intraday_bars_batch(
            symbols=selected_symbols,
            period="1m",
            limit=30,
            max_workers=8,
        )

    def _select_intraday_refresh_symbols(
        self,
        *,
        symbols: list[str],
        materialized: dict[str, LowBuyCandidateOut],
        quote_map: dict[str, object],
        max_symbols: int,
    ) -> list[str]:
        ranked: list[tuple[tuple[int, int, float, float], str]] = []
        for symbol in symbols:
            candidate = materialized.get(symbol)
            quote = quote_map.get(symbol)
            if candidate is None or quote is None:
                continue
            if not self._quote_refresh_needs_intraday(candidate, quote):
                continue
            ranked.append((self._quote_refresh_intraday_rank(candidate, quote), symbol))
        ranked.sort()
        return [symbol for _, symbol in ranked[:max_symbols]]

    def _quote_refresh_needs_intraday(self, candidate: LowBuyCandidateOut, quote) -> bool:
        latest_price = float(getattr(quote, "last_price", 0.0) or 0.0)
        if latest_price <= 0:
            return False
        entry_position = self._entry_position(candidate, latest_price)
        return entry_position in {"in_zone", "below_zone", "near_above_zone"}

    def _quote_refresh_intraday_rank(self, candidate: LowBuyCandidateOut, quote) -> tuple[int, int, float, float]:
        latest_price = float(getattr(quote, "last_price", 0.0) or 0.0)
        state_rank = {
            "buy_now": 0,
            "soft_buy_now": 1,
            "observe_confirmed": 2,
            "near_entry": 3,
            "watch": 4,
        }.get(candidate.buy_signal_state, 5)
        position_rank = {
            "in_zone": 0,
            "below_zone": 1,
            "near_above_zone": 2,
        }.get(self._entry_position(candidate, latest_price), 3)
        entry_distance = distance_to_entry_zone_pct(candidate, latest_price)
        return (state_rank, position_rank, entry_distance, -float(candidate.score or 0.0))

    def _load_quote_refresh_intraday_bars(self, symbol: str):
        try:
            return self.market_data.get_intraday_bars(symbol, period="1m", limit=30)
        except Exception:
            return None

    def _load_cached_candidates_by_symbol(
        self,
        strategy: str,
        latest_trade_date: str,
        symbols: list[str],
    ) -> dict[str, LowBuyCandidateOut]:
        result: dict[str, LowBuyCandidateOut] = {}
        for payload in self._candidate_cache_payloads(strategy, latest_trade_date, full_only=True):
            if payload.performance is None:
                continue
            for candidate in payload.confirmed_candidates + payload.candidates:
                if candidate.symbol in symbols:
                    adjusted = self._apply_strategy_performance_to_candidates(
                        [candidate],
                        payload.performance,
                    )[0]
                    result[candidate.symbol] = adjusted
        return result

    def _load_cached_candidates_by_symbol_any_mode(
        self,
        strategy: str,
        latest_trade_date: str,
        symbols: list[str],
    ) -> dict[str, LowBuyCandidateOut]:
        wanted = set(symbols)
        result: dict[str, LowBuyCandidateOut] = {}
        for payload in self._candidate_cache_payloads(strategy, latest_trade_date, full_only=False):
            if payload.performance is None:
                continue
            for candidate in payload.confirmed_candidates + payload.candidates:
                if candidate.symbol in wanted and candidate.symbol not in result:
                    adjusted = self._apply_strategy_performance_to_candidates(
                        [candidate],
                        payload.performance,
                    )[0]
                    result[candidate.symbol] = adjusted
            if len(result) == len(wanted):
                break
        return result

    def _load_cached_candidate_snapshot_by_symbol_any_mode(
        self,
        strategy: str,
        symbol: str,
    ) -> tuple[LowBuyCandidateOut | None, LowBuyScreenerResponse | None]:
        for payload in self._candidate_cache_payloads(strategy, latest_trade_date=None, full_only=False):
            if payload.performance is None:
                continue
            for candidate in payload.confirmed_candidates + payload.candidates:
                if candidate.symbol == symbol:
                    adjusted = self._apply_strategy_performance_to_candidates(
                        [candidate],
                        payload.performance,
                    )[0]
                    return adjusted, payload
        return None, None

    def _candidate_cache_payloads(
        self,
        strategy: str,
        latest_trade_date: str | None,
        *,
        full_only: bool,
    ) -> list[LowBuyScreenerResponse]:
        now = time.monotonic()
        cached_payloads: list[LowBuyScreenerResponse] = []
        with self._cache_lock:
            for expires_at, payload in self._screen_cache.values():
                if expires_at <= now or not isinstance(payload, LowBuyScreenerResponse):
                    continue
                if payload.strategy_key != strategy:
                    continue
                if latest_trade_date is not None and payload.latest_trade_date != latest_trade_date:
                    continue
                if full_only and payload.response_mode != "full":
                    continue
                cached_payloads.append(payload.model_copy(deep=True))
        cached_payloads.sort(key=self._cache_payload_rank, reverse=True)
        return cached_payloads

    @staticmethod
    def _cache_payload_rank(payload: LowBuyScreenerResponse) -> tuple:
        return (
            1 if payload.response_mode == "full" else 0,
            payload.latest_trade_date,
            payload.active_scan_limit,
            payload.scanned_count,
            payload.as_of_date,
        )
