from __future__ import annotations

from typing import Any

from app.services.low_buy.shared import (
    DEFAULT_PRODUCTION_LOW_BUY_STRATEGY,
    Session,
    normalize_low_buy_strategy,
)


class LowBuyComponent:
    def __init__(self, runtime: Any) -> None:
        self._runtime = runtime

    @staticmethod
    def _strategy(strategy: str | None) -> str | None:
        return normalize_low_buy_strategy(strategy) if strategy else None


class LowBuyScreeningComponent(LowBuyComponent):
    def screen(
        self,
        db: Session,
        strategy: str = DEFAULT_PRODUCTION_LOW_BUY_STRATEGY,
        limit: int = 16,
        scan_limit: int = 72,
        include_history: bool = False,
        scan_mode: str = "quick",
    ):
        return self._runtime.screen(
            db=db,
            strategy=self._strategy(strategy) or DEFAULT_PRODUCTION_LOW_BUY_STRATEGY,
            limit=limit,
            scan_limit=scan_limit,
            include_history=include_history,
            scan_mode=scan_mode,
        )

    def history(self, db: Session, strategy: str = DEFAULT_PRODUCTION_LOW_BUY_STRATEGY):
        return self._runtime.history(db=db, strategy=self._strategy(strategy) or DEFAULT_PRODUCTION_LOW_BUY_STRATEGY)

    def refresh_candidate_quotes(self, db: Session, strategy: str, symbols: list[str]):
        return self._runtime.refresh_candidate_quotes(
            db=db,
            strategy=self._strategy(strategy) or DEFAULT_PRODUCTION_LOW_BUY_STRATEGY,
            symbols=symbols,
        )

    def candidate_by_symbol(
        self,
        db: Session,
        symbol: str,
        strategy: str = DEFAULT_PRODUCTION_LOW_BUY_STRATEGY,
        scan_limit: int = 72,
    ):
        payload = self.screen(
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
        return self._runtime.refresh_full_scan_cache(
            strategy=self._strategy(strategy) or DEFAULT_PRODUCTION_LOW_BUY_STRATEGY,
            limit=limit,
            scan_limit=scan_limit,
            include_history=include_history,
            compute_performance=compute_performance,
            build_close_review=build_close_review,
        )


class LowBuyPriorityComponent(LowBuyComponent):
    def priority_board(self, db: Session, limit: int = 12):
        return self._runtime.priority_board(db=db, limit=limit)


class LowBuyMobileComponent(LowBuyComponent):
    def mobile_snapshot(
        self,
        db: Session,
        strategy: str = DEFAULT_PRODUCTION_LOW_BUY_STRATEGY,
        limit: int = 12,
        fallback_scan_limit: int = 24,
        history_wait_timeout_seconds: float | None = None,
    ):
        return self._runtime.mobile_snapshot(
            db=db,
            strategy=self._strategy(strategy) or DEFAULT_PRODUCTION_LOW_BUY_STRATEGY,
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
        return self._runtime.mobile_candidate_by_symbol(
            db=db,
            symbol=symbol,
            strategy=self._strategy(strategy) or DEFAULT_PRODUCTION_LOW_BUY_STRATEGY,
            detail_limit=detail_limit,
            fallback_scan_limit=fallback_scan_limit,
            history_wait_timeout_seconds=history_wait_timeout_seconds,
        )


class LowBuyLifecycleComponent(LowBuyComponent):
    def sync_trade_lifecycle(self, db: Session, strategy: str | None = None, limit: int = 100):
        return self._runtime.sync_trade_lifecycle(db=db, strategy=self._strategy(strategy), limit=limit)

    def list_trade_lifecycle(self, db: Session, strategy: str | None = None, limit: int = 100):
        return self._runtime.list_trade_lifecycle(db=db, strategy=self._strategy(strategy), limit=limit)

    def update_trade_lifecycle(self, db: Session, symbol: str, payload):
        return self._runtime.update_trade_lifecycle(db=db, symbol=symbol, payload=payload)


class LowBuyBacktestComponent(LowBuyComponent):
    def execution_backtest(
        self,
        db: Session,
        strategy: str = DEFAULT_PRODUCTION_LOW_BUY_STRATEGY,
        lookback_days: int = 60,
        limit: int = 200,
    ):
        return self._runtime.execution_backtest(
            db=db,
            strategy=self._strategy(strategy) or DEFAULT_PRODUCTION_LOW_BUY_STRATEGY,
            lookback_days=lookback_days,
            limit=limit,
        )
