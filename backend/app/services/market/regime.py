from __future__ import annotations

from dataclasses import replace
import threading
import time

import pandas as pd

from app.core.config import get_settings
from app.services.market.regime_persistence import (
    load_persisted_market_regime_snapshot,
    persist_market_regime_snapshot,
)
from app.services.market.regime_cache import (
    get_cached_snapshot,
    set_cached_snapshot,
)
from app.services.market.regime_scoring import (
    classify_market_regime,
    market_breadth_sequence_key,
    market_regime_text,
    normalize_board_frame,
)
from app.services.market.regime_adjustments import (
    apply_market_readiness_guard,
    apply_regime_continuity,
    guarded_states,
    stabilize_market_regime,
)
from app.services.market.regime_breadth import (
    build_market_breadth_snapshot,
    compute_hot_overlap_ratio,
    compute_hot_turnover,
    load_local_daily_breadth_snapshot,
    load_market_breadth_snapshot,
    warm_market_breadth_snapshot_async,
)
from app.services.market.regime_types import (
    STATE_CONFIG,
    MarketBreadthSnapshot,
    MarketRegimeSnapshot,
)
from app.services.market.regime_style import load_style_proxy_changes


class MarketRegimeMixin:
    _recent_hot_industries_cache: tuple[float, list[str]] = (0.0, [])
    _recent_hot_industries_ttl_seconds = 300.0
    _provider_degraded_until: dict[str, float] = {}
    _provider_probe_inflight: set[str] = set()
    _provider_degraded_lock = threading.Lock()
    _provider_degraded_default_cooldown_seconds = 5 * 60.0

    def get_market_regime(
        self,
        *,
        latest_trade_date: str | None = None,
        hot_industries: list[str] | None = None,
        hot_industry_source: str = "",
        hot_industry_source_text: str = "",
        recent_hot_sequences: list[list[str]] | None = None,
    ) -> MarketRegimeSnapshot:
        trade_date = latest_trade_date or self._resolve_regime_trade_date(None) or "intraday"
        cached = self._get_compatible_regime_cache(trade_date, hot_industries)
        if cached is not None:
            return cached

        board_operation = "fetch_board_breadth_frame"
        if self._provider_degraded_recently(board_operation) or self._provider_circuit_open(board_operation):
            return self._provider_degraded_regime_snapshot(
                trade_date=trade_date,
                hot_industries=hot_industries,
                hot_industry_source=hot_industry_source,
                hot_industry_source_text=hot_industry_source_text,
            )

        if not self._try_enter_provider_probe(board_operation):
            return self._provider_degraded_regime_snapshot(
                trade_date=trade_date,
                hot_industries=hot_industries,
                hot_industry_source=hot_industry_source,
                hot_industry_source_text=hot_industry_source_text,
            )
        try:
            board_frame = self._load_board_breadth_frame()
        finally:
            self._exit_provider_probe(board_operation)
        if board_frame is None:
            self._remember_provider_degraded(board_operation)
            return self._provider_degraded_regime_snapshot(
                trade_date=trade_date,
                hot_industries=hot_industries,
                hot_industry_source=hot_industry_source,
                hot_industry_source_text=hot_industry_source_text,
            )
        self._clear_provider_degraded(board_operation)
        snapshot = classify_market_regime(
            board_frame,
            limit_down_count=self._load_limit_down_count_cached(
                trade_date if trade_date != "intraday" else None
            ),
            hot_industries=self._resolve_hot_industries(board_frame, hot_industries),
            hot_industry_source=hot_industry_source
            or ("board_strength" if board_frame is not None else "unavailable"),
            hot_industry_source_text=hot_industry_source_text
            or (
                "热点来源：板块涨幅实时榜"
                if board_frame is not None
                else "热点来源：暂无有效归因"
            ),
            breadth_snapshot=self._load_market_breadth_snapshot(recent_hot_sequences),
            emotion_snapshot=self._load_market_emotion_snapshot(
                trade_date if trade_date != "intraday" else None
            ),
        )
        snapshot = self._stabilize_market_regime(
            snapshot,
            self._peek_market_regime_snapshot(trade_date),
        )
        snapshot = self._apply_market_readiness_guard(snapshot)
        snapshot = self._apply_regime_continuity(
            snapshot,
            self._peek_market_regime_snapshot(trade_date),
        )
        snapshot = replace(
            snapshot,
            snapshot_source="live" if board_frame is not None else "warming",
            snapshot_source_text=(
                "实时市场快照"
                if board_frame is not None
                else "实时 provider 暂不可用，使用本地/轻量市场状态"
            ),
        )
        self._set_market_regime_cache(trade_date, snapshot)
        self._persist_market_regime_snapshot(trade_date, snapshot)
        return snapshot

    def get_market_regime_fast(
        self,
        *,
        latest_trade_date: str | None = None,
        hot_industries: list[str] | None = None,
        hot_industry_source: str = "",
        hot_industry_source_text: str = "",
        recent_hot_sequences: list[list[str]] | None = None,
    ) -> MarketRegimeSnapshot:
        trade_date = latest_trade_date or self._resolve_regime_trade_date(None) or "intraday"
        cached = self._get_compatible_regime_cache(trade_date, hot_industries)
        if cached is not None:
            return cached
        self._warm_market_regime_snapshot_async(
            trade_date=trade_date,
            hot_industries=hot_industries or [],
            hot_industry_source=hot_industry_source,
            hot_industry_source_text=hot_industry_source_text,
            recent_hot_sequences=recent_hot_sequences or [],
        )
        persisted = self._load_persisted_market_regime_snapshot(trade_date, hot_industries)
        if persisted is not None:
            self._set_market_regime_cache(trade_date, persisted)
            return persisted
        return self._build_lightweight_market_regime(
            hot_industries=hot_industries or [],
            hot_industry_source=hot_industry_source,
            hot_industry_source_text=hot_industry_source_text,
        )

    def _warm_market_regime_snapshot_async(
        self,
        *,
        trade_date: str,
        hot_industries: list[str],
        hot_industry_source: str,
        hot_industry_source_text: str,
        recent_hot_sequences: list[list[str]],
    ) -> None:
        with self._cache_lock:
            if trade_date in self._market_regime_jobs:
                return
            self._market_regime_jobs.add(trade_date)

        def runner() -> None:
            try:
                self.get_market_regime(
                    latest_trade_date=None if trade_date == "intraday" else trade_date,
                    hot_industries=hot_industries,
                    hot_industry_source=hot_industry_source,
                    hot_industry_source_text=hot_industry_source_text,
                    recent_hot_sequences=recent_hot_sequences,
                )
            finally:
                with self._cache_lock:
                    self._market_regime_jobs.discard(trade_date)

        threading.Thread(target=runner, name=f"market-regime-{trade_date}", daemon=True).start()

    @staticmethod
    def _build_lightweight_market_regime(
        *,
        hot_industries: list[str],
        hot_industry_source: str,
        hot_industry_source_text: str,
    ) -> MarketRegimeSnapshot:
        snapshot = classify_market_regime(
            None,
            limit_down_count=None,
            hot_industries=hot_industries,
            hot_industry_source=hot_industry_source or "cached_fallback",
            hot_industry_source_text=hot_industry_source_text or "热点来源：后台补齐中",
        )
        return replace(
            snapshot,
            snapshot_source="warming",
            snapshot_source_text="市场状态正在刷新，暂用轻量快照",
        )

    def _get_compatible_regime_cache(
        self,
        cache_key: str,
        hot_industries: list[str] | None,
    ) -> MarketRegimeSnapshot | None:
        cached = self._get_market_regime_cache(cache_key)
        if cached is not None and (not hot_industries or hot_industries == cached.hot_industries):
            return cached
        return None

    @classmethod
    def _resolve_hot_industries(
        cls,
        board_frame: pd.DataFrame | None,
        hot_industries: list[str] | None,
    ) -> list[str]:
        if hot_industries:
            cls._remember_hot_industries(hot_industries)
            return hot_industries
        if board_frame is None:
            return cls._recent_hot_industries()
        resolved = board_frame.head(3)["industry"].tolist()
        cls._remember_hot_industries(resolved)
        return resolved

    @classmethod
    def _remember_hot_industries(cls, industries: list[str]) -> None:
        values = [item for item in industries if item]
        if values:
            cls._recent_hot_industries_cache = (
                time.monotonic() + cls._recent_hot_industries_ttl_seconds,
                values,
            )

    @classmethod
    def _recent_hot_industries(cls) -> list[str]:
        expires_at, values = cls._recent_hot_industries_cache
        if time.monotonic() < expires_at:
            return list(values)
        return []

    def _stabilize_market_regime(
        self,
        snapshot: MarketRegimeSnapshot,
        previous_snapshot: MarketRegimeSnapshot | None,
    ) -> MarketRegimeSnapshot:
        return stabilize_market_regime(snapshot, previous_snapshot)

    @staticmethod
    def _apply_regime_continuity(
        snapshot: MarketRegimeSnapshot,
        previous_snapshot: MarketRegimeSnapshot | None,
    ) -> MarketRegimeSnapshot:
        return apply_regime_continuity(snapshot, previous_snapshot)

    def _apply_market_readiness_guard(self, snapshot: MarketRegimeSnapshot) -> MarketRegimeSnapshot:
        return apply_market_readiness_guard(snapshot)

    @staticmethod
    def _guarded_states() -> set[str]:
        return guarded_states()

    def _load_board_breadth_frame(self) -> pd.DataFrame | None:
        result = self.provider_router.fetch_board_breadth_frame()
        if result.usable and result.data is not None:
            return normalize_board_frame(result.data)
        return None

    def _provider_circuit_open(self, operation: str) -> bool:
        checker = getattr(self.provider_router, "all_providers_circuit_open", None)
        if not callable(checker):
            return False
        try:
            return bool(checker(operation))
        except Exception:
            return False

    def _provider_degraded_regime_snapshot(
        self,
        *,
        trade_date: str,
        hot_industries: list[str] | None,
        hot_industry_source: str,
        hot_industry_source_text: str,
    ) -> MarketRegimeSnapshot:
        persisted = self._load_persisted_market_regime_snapshot(trade_date, hot_industries)
        if persisted is not None:
            self._set_market_regime_cache(trade_date, persisted)
            return persisted
        snapshot = self._build_lightweight_market_regime(
            hot_industries=hot_industries or self._recent_hot_industries(),
            hot_industry_source=hot_industry_source or "cached_fallback",
            hot_industry_source_text=hot_industry_source_text or "热点来源：provider 退化，暂用轻量快照",
        )
        self._set_market_regime_cache(trade_date, snapshot)
        return snapshot

    @classmethod
    def _provider_degraded_recently(cls, operation: str) -> bool:
        with cls._provider_degraded_lock:
            return cls._provider_degraded_until.get(operation, 0.0) > time.monotonic()

    @classmethod
    def _remember_provider_degraded(cls, operation: str) -> None:
        with cls._provider_degraded_lock:
            cls._provider_degraded_until[operation] = (
                time.monotonic() + cls._provider_degraded_cooldown_seconds()
            )

    @classmethod
    def _provider_degraded_cooldown_seconds(cls) -> float:
        try:
            value = get_settings().market_regime_provider_degraded_cooldown_seconds
        except Exception:
            return cls._provider_degraded_default_cooldown_seconds
        try:
            return max(float(value), 0.0)
        except (TypeError, ValueError):
            return cls._provider_degraded_default_cooldown_seconds

    @classmethod
    def _clear_provider_degraded(cls, operation: str) -> None:
        with cls._provider_degraded_lock:
            cls._provider_degraded_until.pop(operation, None)

    @classmethod
    def _try_enter_provider_probe(cls, operation: str) -> bool:
        with cls._provider_degraded_lock:
            if operation in cls._provider_probe_inflight:
                return False
            cls._provider_probe_inflight.add(operation)
            return True

    @classmethod
    def _exit_provider_probe(cls, operation: str) -> None:
        with cls._provider_degraded_lock:
            cls._provider_probe_inflight.discard(operation)

    def _load_market_breadth_snapshot(
        self,
        recent_hot_sequences: list[list[str]] | None = None,
    ) -> MarketBreadthSnapshot:
        return load_market_breadth_snapshot(self, recent_hot_sequences)

    def _load_local_daily_breadth_snapshot(
        self,
        recent_hot_sequences: list[list[str]],
    ) -> MarketBreadthSnapshot | None:
        return load_local_daily_breadth_snapshot(self, recent_hot_sequences)

    def _warm_market_breadth_snapshot_async(
        self,
        cache_key: str,
        recent_hot_sequences: list[list[str]],
    ) -> None:
        warm_market_breadth_snapshot_async(self, cache_key, recent_hot_sequences)

    def _build_market_breadth_snapshot(
        self,
        *,
        snapshot_map,
        recent_hot_sequences: list[list[str]],
        breadth_ready: bool,
    ) -> MarketBreadthSnapshot:
        return build_market_breadth_snapshot(
            self,
            snapshot_map=snapshot_map,
            recent_hot_sequences=recent_hot_sequences,
            breadth_ready=breadth_ready,
        )

    @staticmethod
    def _market_breadth_cache_key(recent_hot_sequences: list[list[str]] | None) -> str:
        return market_breadth_sequence_key(recent_hot_sequences or [])

    def _load_style_proxy_changes(self) -> tuple[float, float]:
        return load_style_proxy_changes(self.get_quotes_batch)

    @staticmethod
    def _compute_hot_turnover(sequences: list[list[str]]) -> float:
        return compute_hot_turnover(sequences)

    @staticmethod
    def _compute_hot_overlap_ratio(sequences: list[list[str]]) -> float:
        return compute_hot_overlap_ratio(sequences)

    def _load_limit_down_count_cached(self, latest_trade_date: str | None) -> int | None:
        cache_key = latest_trade_date or "intraday"
        cached = self._get_limit_down_cache(cache_key)
        if cached is not None:
            return cached
        if not latest_trade_date:
            return None
        try:
            frame = None
            if self._market_provider_router_enabled():
                routed = self.provider_router.fetch_limit_down_pool(latest_trade_date)
                if routed.usable:
                    frame = routed.data
                else:
                    return None
            else:
                return None
        except Exception:
            return None
        count = int(len(frame.index)) if frame is not None else 0
        self._set_limit_down_cache(cache_key, count)
        return count

    def _get_market_regime_cache(self, key: str) -> MarketRegimeSnapshot | None:
        return self._get_cached_snapshot(
            self._market_regime_cache,
            self._market_regime_cache_ttl,
            key,
        )

    def _peek_market_regime_snapshot(self, key: str) -> MarketRegimeSnapshot | None:
        with self._cache_lock:
            cached = self._market_regime_cache.get(key)
            if cached is None:
                return None
            return cached[1]

    def _get_market_breadth_cache(self, key: str) -> MarketBreadthSnapshot | None:
        return self._get_cached_snapshot(
            self._market_breadth_cache,
            self._market_breadth_cache_ttl,
            key,
        )

    def _set_market_breadth_cache(self, key: str, snapshot: MarketBreadthSnapshot) -> None:
        self._set_cached_snapshot(
            self._market_breadth_cache,
            self._market_breadth_cache_ttl,
            key,
            snapshot,
        )

    def _set_market_regime_cache(self, key: str, snapshot: MarketRegimeSnapshot) -> None:
        self._set_cached_snapshot(
            self._market_regime_cache,
            self._market_regime_cache_ttl,
            key,
            snapshot,
        )

    def _persist_market_regime_snapshot(self, key: str, snapshot: MarketRegimeSnapshot) -> None:
        persist_market_regime_snapshot(key, snapshot)

    def _load_persisted_market_regime_snapshot(
        self,
        key: str,
        hot_industries: list[str] | None,
    ) -> MarketRegimeSnapshot | None:
        return load_persisted_market_regime_snapshot(key, hot_industries)

    def _get_limit_down_cache(self, key: str) -> int | None:
        return self._get_cached_snapshot(self._limit_down_cache, self._limit_down_cache_ttl, key)

    def _set_limit_down_cache(self, key: str, value: int) -> None:
        self._set_cached_snapshot(self._limit_down_cache, self._limit_down_cache_ttl, key, value)

    def _get_cached_snapshot(self, store: dict[str, tuple[float, object]], ttl: float, key: str):
        return get_cached_snapshot(store, self._cache_lock, key)

    def _set_cached_snapshot(
        self,
        store: dict[str, tuple[float, object]],
        ttl: float,
        key: str,
        payload: object,
    ) -> None:
        set_cached_snapshot(store, self._cache_lock, ttl=ttl, key=key, payload=payload)

__all__ = [
    "MarketBreadthSnapshot",
    "MarketRegimeMixin",
    "MarketRegimeSnapshot",
    "STATE_CONFIG",
    "classify_market_regime",
    "market_regime_text",
    "normalize_board_frame",
]
