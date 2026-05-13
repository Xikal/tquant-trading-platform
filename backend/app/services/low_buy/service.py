from __future__ import annotations

import threading
import time
from types import MethodType
from typing import Any

from app.services.low_buy.candidate import LowBuyCandidateMixin
from app.services.low_buy.close_review import LowBuyCloseReviewMixin
from app.services.low_buy.execution_backtest import LowBuyExecutionBacktestMixin
from app.services.low_buy.history import LowBuyHistoryMixin
from app.services.low_buy.hot_industry_context import LowBuyHotIndustryContextMixin
from app.services.low_buy.lifecycle import LowBuyLifecycleMixin
from app.services.low_buy.mobile import LowBuyMobileReadMixin
from app.services.low_buy.performance import LowBuyPerformanceMixin
from app.services.low_buy.pool import LowBuyPoolMixin
from app.services.low_buy.priority_board import LowBuyPriorityBoardMixin
from app.services.low_buy.results import LowBuyResultStoreMixin
from app.services.low_buy.screening import LowBuyScreeningMixin
from app.services.low_buy.service_components import (
    LowBuyBacktestComponent,
    LowBuyLifecycleComponent,
    LowBuyMobileComponent,
    LowBuyPriorityComponent,
    LowBuyScreeningComponent,
)
from app.services.low_buy.signals import LowBuySignalMixin
from app.services.low_buy.shared import (
    DEFAULT_PRODUCTION_LOW_BUY_STRATEGY,
    LowBuyHistoryResponse,
    MarketDataService,
    Session,
    pd,
)


class _LowBuyRuntimeAdapter:
    """Composition adapter that exposes legacy mixin methods without inheriting them.

    The low-buy implementation still reuses legacy mixin functions, but the
    runtime component now *contains* the mixin class instead of subclassing it.
    This removes the remaining MRO dependency while keeping behavior stable for
    the large strategy surface.
    """

    def __init__(self, runtime: "_LowBuyRuntime", mixin_cls: type) -> None:
        object.__setattr__(self, "_runtime", runtime)
        object.__setattr__(self, "_mixin_cls", mixin_cls)

    def __getattr__(self, name: str) -> Any:
        mixin_cls = object.__getattribute__(self, "_mixin_cls")
        for cls in mixin_cls.mro():
            if cls is object:
                continue
            if name not in cls.__dict__:
                continue
            value = cls.__dict__[name]
            if isinstance(value, staticmethod):
                return value.__func__
            if isinstance(value, classmethod):
                raise AttributeError(f"classmethod {name!r} is not exposed through low-buy adapters")
            if callable(value):
                return MethodType(value, self)
            runtime = object.__getattribute__(self, "_runtime")
            if hasattr(runtime, name):
                return getattr(runtime, name)
            return value
        return getattr(object.__getattribute__(self, "_runtime"), name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "_runtime":
            object.__setattr__(self, name, value)
            return
        setattr(object.__getattribute__(self, "_runtime"), name, value)

    def _get_screen_cache(self, cache_key: str):
        return self._runtime._get_screen_cache(cache_key)

    def _set_screen_cache(self, cache_key: str, payload, ttl: float | None = None) -> None:
        self._runtime._set_screen_cache(cache_key, payload, ttl=ttl)

    def _get_history_cache(self, cache_key: str):
        return self._runtime._get_history_cache(cache_key)

    def _set_history_cache(self, cache_key: str, payload: LowBuyHistoryResponse) -> None:
        self._runtime._set_history_cache(cache_key, payload)

    def _get_daily_history_cache(self, cache_key: str):
        return self._runtime._get_daily_history_cache(cache_key)

    def _set_daily_history_cache(self, cache_key: str, payload: pd.DataFrame | None) -> None:
        self._runtime._set_daily_history_cache(cache_key, payload)

    def _get_spot_quote_cache(self):
        return self._runtime._get_spot_quote_cache()

    def _set_spot_quote_cache(self, payload) -> None:
        self._runtime._set_spot_quote_cache(payload)


class _LowBuyRuntime:
    """Composed low-buy runtime.

    Legacy mixin implementations are kept as adapters, but the runtime itself is
    no longer a multiple-inheritance endpoint.  This provides a stable seam for
    gradually moving each adapter into native service classes without changing
    strategy semantics in one large rewrite.
    """

    _runtime_mixin_classes = (
        LowBuyExecutionBacktestMixin,
        LowBuyLifecycleMixin,
        LowBuyCloseReviewMixin,
        LowBuyPerformanceMixin,
        LowBuyHistoryMixin,
        LowBuyMobileReadMixin,
        LowBuySignalMixin,
        LowBuyPriorityBoardMixin,
        LowBuyCandidateMixin,
        LowBuyHotIndustryContextMixin,
        LowBuyPoolMixin,
        LowBuyResultStoreMixin,
        LowBuyScreeningMixin,
    )
    _full_cache_setting_prefix = "low_buy_full_cache"
    _screen_cache = {}
    _daily_history_cache = {}
    _spot_quote_cache = None
    _full_scan_jobs = {}
    _priority_base_cache = {}
    _priority_response_cache = {}
    _quote_refresh_response_cache = {}
    _trade_dates_cache = {}
    _confirmed_signal_states = ("buy_now", "soft_buy_now")
    _cache_lock = threading.Lock()
    _screen_cache_ttl = 300.0
    _screen_cache_ttl_full = 300.0
    _daily_history_cache_ttl = 300.0
    _spot_quote_cache_ttl = 12.0
    _priority_base_cache_ttl = 120.0
    _priority_response_cache_ttl = 30.0
    _quote_refresh_response_cache_ttl = 8.0
    _trade_dates_cache_ttl = 3600.0
    _default_full_scan_limit = 480

    def __init__(self) -> None:
        self.market_data = MarketDataService()
        self._adapters = [_LowBuyRuntimeAdapter(self, mixin_cls) for mixin_cls in self._runtime_mixin_classes]
        self._method_map = _build_runtime_method_map(self._adapters)

    def __getattr__(self, name: str) -> Any:
        adapter = self._method_map.get(name)
        if adapter is None:
            raise AttributeError(f"{self.__class__.__name__!s} has no attribute {name!r}")
        return getattr(adapter, name)

    def _get_screen_cache(self, cache_key: str):
        cls = type(self)
        now = time.monotonic()
        with cls._cache_lock:
            cached = cls._screen_cache.get(cache_key)
            if cached is None:
                return None
            expires_at, payload = cached
            if expires_at <= now:
                cls._screen_cache.pop(cache_key, None)
                return None
            return payload.model_copy(deep=True)

    def _set_screen_cache(self, cache_key: str, payload, ttl: float | None = None) -> None:
        cls = type(self)
        with cls._cache_lock:
            cls._screen_cache[cache_key] = (
                time.monotonic() + (ttl or cls._screen_cache_ttl),
                payload.model_copy(deep=True),
            )

    def _get_history_cache(self, cache_key: str):
        cls = type(self)
        now = time.monotonic()
        with cls._cache_lock:
            cached = cls._screen_cache.get(cache_key)
            if cached is None:
                return None
            expires_at, payload = cached
            if expires_at <= now:
                cls._screen_cache.pop(cache_key, None)
                return None
            if isinstance(payload, LowBuyHistoryResponse):
                return payload.model_copy(deep=True)
            return None

    def _set_history_cache(self, cache_key: str, payload: LowBuyHistoryResponse) -> None:
        cls = type(self)
        with cls._cache_lock:
            cls._screen_cache[cache_key] = (
                time.monotonic() + cls._screen_cache_ttl,
                payload.model_copy(deep=True),
            )

    def _get_daily_history_cache(self, cache_key: str):
        cls = type(self)
        now = time.monotonic()
        with cls._cache_lock:
            cached = cls._daily_history_cache.get(cache_key)
            if cached is None:
                return None
            expires_at, payload = cached
            if expires_at <= now:
                cls._daily_history_cache.pop(cache_key, None)
                return None
            return payload

    def _set_daily_history_cache(self, cache_key: str, payload: pd.DataFrame | None) -> None:
        cls = type(self)
        with cls._cache_lock:
            cls._daily_history_cache[cache_key] = (
                time.monotonic() + cls._daily_history_cache_ttl,
                payload.copy(deep=True) if payload is not None else None,
            )

    def _get_spot_quote_cache(self):
        cls = type(self)
        now = time.monotonic()
        with cls._cache_lock:
            cached = cls._spot_quote_cache
            if cached is None:
                return None
            expires_at, payload = cached
            if expires_at <= now:
                cls._spot_quote_cache = None
                return None
            return dict(payload)

    def _set_spot_quote_cache(self, payload) -> None:
        cls = type(self)
        with cls._cache_lock:
            cls._spot_quote_cache = (time.monotonic() + cls._spot_quote_cache_ttl, dict(payload))

    @classmethod
    def clear_runtime_caches(cls) -> None:
        with cls._cache_lock:
            cls._screen_cache.clear()
            cls._daily_history_cache.clear()
            cls._spot_quote_cache = None
            cls._full_scan_jobs.clear()
            cls._priority_base_cache.clear()
            cls._priority_response_cache.clear()
            cls._quote_refresh_response_cache.clear()
            cls._trade_dates_cache.clear()

    @classmethod
    def clear_all_caches(cls) -> None:
        cls.clear_runtime_caches()


def _build_runtime_method_map(adapters: list[_LowBuyRuntimeAdapter]) -> dict[str, _LowBuyRuntimeAdapter]:
    method_map: dict[str, _LowBuyRuntimeAdapter] = {}
    for adapter in adapters:
        mixin_cls = object.__getattribute__(adapter, "_mixin_cls")
        for cls in mixin_cls.mro():
            if cls is object:
                continue
            for name, value in cls.__dict__.items():
                if name.startswith("__") or name in method_map:
                    continue
                if isinstance(value, classmethod):
                    continue
                if callable(value) or isinstance(value, staticmethod):
                    method_map[name] = adapter
    return method_map


class LowBuyScreenerService:
    def __init__(self) -> None:
        self._runtime = _LowBuyRuntime()
        self._screening = LowBuyScreeningComponent(self._runtime)
        self._priority = LowBuyPriorityComponent(self._runtime)
        self._mobile = LowBuyMobileComponent(self._runtime)
        self._lifecycle = LowBuyLifecycleComponent(self._runtime)
        self._backtest = LowBuyBacktestComponent(self._runtime)

    def __getattr__(self, name: str) -> Any:
        """Compatibility seam for legacy tests and internal helpers.

        Public callers should use the explicit component methods above.  This
        keeps older private method probes working while the implementation is
        moved from mixins to composed adapters.
        """

        return getattr(self._runtime, name)

    def screen(
        self,
        db: Session,
        strategy: str = DEFAULT_PRODUCTION_LOW_BUY_STRATEGY,
        limit: int = 16,
        scan_limit: int = 72,
        include_history: bool = False,
        scan_mode: str = "quick",
    ):
        return self._screening.screen(
            db=db,
            strategy=strategy,
            limit=limit,
            scan_limit=scan_limit,
            include_history=include_history,
            scan_mode=scan_mode,
        )

    def history(self, db: Session, strategy: str = DEFAULT_PRODUCTION_LOW_BUY_STRATEGY):
        return self._screening.history(db=db, strategy=strategy)

    def refresh_candidate_quotes(self, db: Session, strategy: str, symbols: list[str]):
        return self._screening.refresh_candidate_quotes(db=db, strategy=strategy, symbols=symbols)

    def priority_board(self, db: Session, limit: int = 12):
        return self._priority.priority_board(db=db, limit=limit)

    def mobile_snapshot(
        self,
        db: Session,
        strategy: str = DEFAULT_PRODUCTION_LOW_BUY_STRATEGY,
        limit: int = 12,
        fallback_scan_limit: int = 24,
        history_wait_timeout_seconds: float | None = None,
    ):
        return self._mobile.mobile_snapshot(
            db=db,
            strategy=strategy,
            limit=limit,
            fallback_scan_limit=fallback_scan_limit,
            history_wait_timeout_seconds=history_wait_timeout_seconds,
        )

    def mobile_candidate_by_symbol(
        self,
        db: Session,
        symbol: str,
        strategy: str = DEFAULT_PRODUCTION_LOW_BUY_STRATEGY,
        detail_limit: int = 24,
        fallback_scan_limit: int = 24,
        history_wait_timeout_seconds: float | None = None,
    ):
        return self._mobile.mobile_candidate_by_symbol(
            db=db,
            symbol=symbol,
            strategy=strategy,
            detail_limit=detail_limit,
            fallback_scan_limit=fallback_scan_limit,
            history_wait_timeout_seconds=history_wait_timeout_seconds,
        )

    def candidate_by_symbol(
        self,
        db: Session,
        symbol: str,
        strategy: str = DEFAULT_PRODUCTION_LOW_BUY_STRATEGY,
        scan_limit: int = 72,
    ):
        return self._screening.candidate_by_symbol(db=db, symbol=symbol, strategy=strategy, scan_limit=scan_limit)

    def refresh_full_scan_cache(
        self,
        strategy: str,
        limit: int,
        scan_limit: int,
        include_history: bool,
        compute_performance: bool,
        build_close_review: bool = True,
    ):
        return self._screening.refresh_full_scan_cache(
            strategy=strategy,
            limit=limit,
            scan_limit=scan_limit,
            include_history=include_history,
            compute_performance=compute_performance,
            build_close_review=build_close_review,
        )

    def sync_trade_lifecycle(self, db: Session, strategy: str | None = None, limit: int = 100):
        return self._lifecycle.sync_trade_lifecycle(db=db, strategy=strategy, limit=limit)

    def list_trade_lifecycle(self, db: Session, strategy: str | None = None, limit: int = 100):
        return self._lifecycle.list_trade_lifecycle(db=db, strategy=strategy, limit=limit)

    def update_trade_lifecycle(self, db: Session, symbol: str, payload):
        return self._lifecycle.update_trade_lifecycle(db=db, symbol=symbol, payload=payload)

    def execution_backtest(
        self,
        db: Session,
        strategy: str = DEFAULT_PRODUCTION_LOW_BUY_STRATEGY,
        lookback_days: int = 60,
        limit: int = 200,
    ):
        return self._backtest.execution_backtest(
            db=db,
            strategy=strategy,
            lookback_days=lookback_days,
            limit=limit,
        )

    def reset_runtime_caches(self) -> None:
        self._runtime.clear_runtime_caches()


def clear_all_low_buy_runtime_caches() -> None:
    """Clear all low-buy runtime caches for tests and admin maintenance."""

    _LowBuyRuntime.clear_runtime_caches()


def clear_all_runtime_caches() -> None:
    """Compatibility alias required by the v4 cache-isolation contract."""

    clear_all_low_buy_runtime_caches()
