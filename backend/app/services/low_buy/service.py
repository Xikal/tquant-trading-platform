from __future__ import annotations

import threading

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
from app.services.low_buy.signals import LowBuySignalMixin
from app.services.low_buy.shared import (
    DEFAULT_PRODUCTION_LOW_BUY_STRATEGY,
    MarketDataService,
    Session,
    normalize_low_buy_strategy,
)


# MRO is intentional: public orchestration methods live in the leftmost mixins,
# while shared read/write helpers stay near the right. Keep new mixins narrow and
# avoid duplicate method names unless explicitly overriding behavior.
class _LowBuyRuntime(
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
):
    _full_cache_setting_prefix = "low_buy_full_cache"
    _screen_cache = {}
    _daily_history_cache = {}
    _spot_quote_cache = None
    _full_scan_jobs = {}
    _priority_base_cache = {}
    _priority_response_cache = {}
    _quote_refresh_response_cache = {}
    _trade_dates_cache = {}
    _cache_lock = threading.Lock()
    _screen_cache_ttl = 300.0
    _screen_cache_ttl_full = 300.0
    _daily_history_cache_ttl = 300.0
    _spot_quote_cache_ttl = 12.0
    _priority_base_cache_ttl = 120.0
    _priority_response_cache_ttl = 8.0
    _quote_refresh_response_cache_ttl = 8.0
    _trade_dates_cache_ttl = 3600.0
    _default_full_scan_limit = 480

    def __init__(self) -> None:
        self.market_data = MarketDataService()


class LowBuyScreenerService:
    def __init__(self) -> None:
        self._runtime = _LowBuyRuntime()

    def __getattr__(self, name: str):
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
        strategy = normalize_low_buy_strategy(strategy)
        return self._runtime.screen(
            db=db,
            strategy=strategy,
            limit=limit,
            scan_limit=scan_limit,
            include_history=include_history,
            scan_mode=scan_mode,
        )

    def history(self, db: Session, strategy: str = DEFAULT_PRODUCTION_LOW_BUY_STRATEGY):
        strategy = normalize_low_buy_strategy(strategy)
        return self._runtime.history(db=db, strategy=strategy)

    def refresh_candidate_quotes(self, db: Session, strategy: str, symbols: list[str]):
        strategy = normalize_low_buy_strategy(strategy)
        return self._runtime.refresh_candidate_quotes(db=db, strategy=strategy, symbols=symbols)

    def priority_board(self, db: Session, limit: int = 12):
        return self._runtime.priority_board(db=db, limit=limit)

    def mobile_snapshot(
        self,
        db: Session,
        strategy: str = DEFAULT_PRODUCTION_LOW_BUY_STRATEGY,
        limit: int = 12,
        fallback_scan_limit: int = 24,
        history_wait_timeout_seconds: float | None = None,
    ):
        strategy = normalize_low_buy_strategy(strategy)
        return self._runtime.mobile_snapshot(
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
        strategy = normalize_low_buy_strategy(strategy)
        return self._runtime.mobile_candidate_by_symbol(
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
        strategy = normalize_low_buy_strategy(strategy)
        payload = self._runtime.screen(
            db=db,
            strategy=strategy,
            limit=min(40, max(16, scan_limit)),
            scan_limit=scan_limit,
            include_history=False,
            scan_mode="full",
        )
        for item in payload.confirmed_candidates + payload.candidates:
            if item.symbol == symbol:
                return item, payload
        return None, payload

    def refresh_full_scan_cache(
        self,
        strategy: str,
        limit: int,
        scan_limit: int,
        include_history: bool,
        compute_performance: bool,
        build_close_review: bool = True,
    ):
        strategy = normalize_low_buy_strategy(strategy)
        return self._runtime.refresh_full_scan_cache(
            strategy=strategy,
            limit=limit,
            scan_limit=scan_limit,
            include_history=include_history,
            compute_performance=compute_performance,
            build_close_review=build_close_review,
        )

    def sync_trade_lifecycle(self, db: Session, strategy: str | None = None, limit: int = 100):
        strategy = normalize_low_buy_strategy(strategy) if strategy else None
        return self._runtime.sync_trade_lifecycle(db=db, strategy=strategy, limit=limit)

    def list_trade_lifecycle(self, db: Session, strategy: str | None = None, limit: int = 100):
        strategy = normalize_low_buy_strategy(strategy) if strategy else None
        return self._runtime.list_trade_lifecycle(db=db, strategy=strategy, limit=limit)

    def execution_backtest(
        self,
        db: Session,
        strategy: str = DEFAULT_PRODUCTION_LOW_BUY_STRATEGY,
        lookback_days: int = 60,
        limit: int = 200,
    ):
        strategy = normalize_low_buy_strategy(strategy)
        return self._runtime.execution_backtest(
            db=db,
            strategy=strategy,
            lookback_days=lookback_days,
            limit=limit,
        )
