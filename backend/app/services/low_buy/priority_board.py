from __future__ import annotations

from copy import deepcopy

from sqlalchemy import select

from app.models.entities import Watchlist
from app.models.schemas import (
    LowBuyCandidateOut,
    LowBuyPriorityBoardItemOut,
    LowBuyPriorityBoardResponse,
    LowBuyStrategyPerformanceOut,
)
from app.services.low_buy.priority_scoring import LowBuyPriorityScoringMixin
from app.services.low_buy.priority_cache import (
    get_priority_base_cache,
    get_priority_response_cache,
    set_priority_base_cache,
    set_priority_response_cache,
)
from app.services.low_buy.priority_types import (
    PriorityBaseSnapshot,
    PriorityCandidate,
    PriorityMarketContext,
    StrategyHit,
)
from app.services.low_buy.priority_family import (
    build_family_performance,
    build_priority_family_sections,
    priority_recommendation_duration_text,
    recommendation_days_by_title,
    strategy_performance_text,
)
from app.services.low_buy.priority_holdings import (
    build_priority_portfolio_risk,
    select_primary_candidates_for_portfolio,
)
from app.services.low_buy.priority_items import build_priority_items
from app.services.low_buy.priority_market import build_market_context
from app.services.low_buy.priority_merging import (
    attach_priority_recommendation_durations,
    collect_priority_candidates,
    display_strategy_titles,
    recommendation_days_by_hit_title,
    upsert_strategy_hit,
)
from app.services.low_buy.priority_performance import build_strategy_hit
from app.services.low_buy.priority_refresh import (
    load_priority_intraday_bars,
    priority_intraday_rank,
    priority_needs_intraday_confirmation,
    refresh_priority_candidates,
)
from app.services.low_buy.priority_response import build_priority_board_response
from app.services.low_buy.priority_snapshot import build_priority_base_snapshot
from app.services.low_buy.shared import (
    LOW_BUY_THRESHOLDS,
    PERFORMANCE_LOOKBACK_DAYS,
    RECENT_PERFORMANCE_LOOKBACK_DAYS,
    Session,
)
from app.services.market.board_exclusions import is_growth_board_stock


class LowBuyPriorityBoardMixin(LowBuyPriorityScoringMixin):
    def priority_board(self, db: Session, limit: int = 12) -> LowBuyPriorityBoardResponse:
        cache_key = f"limit={limit}"
        cached_response = self._get_priority_response_cache(cache_key)
        if cached_response is not None:
            return cached_response

        base_snapshot = self._load_priority_base_snapshot(db=db, limit=limit)
        refreshed_candidates = self._refresh_priority_candidates(base_snapshot.candidates)
        refreshed_candidates = self._attach_priority_recommendation_durations(
            db=db,
            rows=refreshed_candidates,
            latest_trade_date=base_snapshot.latest_trade_date,
        )
        refreshed_candidates = filter_priority_candidates_for_recommendation(refreshed_candidates)
        items = self._build_priority_items(
            refreshed_candidates,
            market_context=base_snapshot.market_context,
        )
        items.sort(key=lambda item: item.priority_score, reverse=True)
        family_performance = build_family_performance(refreshed_candidates)
        family_sections = build_priority_family_sections(
            items=items,
            family_performance=family_performance,
        )
        snapshot_warning = self._priority_snapshot_warning(base_snapshot)
        portfolio_risk = build_priority_portfolio_risk(
            db=db,
            rows=refreshed_candidates,
            market_context=base_snapshot.market_context,
            selector=self,
        )
        response = build_priority_board_response(
            base_snapshot=base_snapshot,
            items=items,
            item_limit=limit,
            family_sections=family_sections,
            portfolio_risk=portfolio_risk,
            snapshot_warning=snapshot_warning,
            market_state_text=self._market_state_text(base_snapshot.market_context),
        )
        self._set_priority_response_cache(cache_key, response)
        return response

    def _load_priority_base_snapshot(self, db: Session, limit: int) -> PriorityBaseSnapshot:
        cache_key = f"limit={limit}"
        cached = self._get_priority_base_cache(cache_key)
        if cached is not None:
            return cached
        snapshot = self._build_priority_base_snapshot(db=db, limit=limit)
        self._set_priority_base_cache(cache_key, snapshot)
        return deepcopy(snapshot)

    def _build_priority_base_snapshot(self, db: Session, limit: int) -> PriorityBaseSnapshot:
        return build_priority_base_snapshot(builder=self, db=db, limit=limit)

    def _resolve_priority_target_trade_date(self) -> str:
        trade_dates = self._get_recent_trade_dates(14)
        if len(trade_dates) < 3:
            return ""
        return self._resolve_latest_completed_trade_date(trade_dates)

    @staticmethod
    def _priority_snapshot_warning(snapshot: PriorityBaseSnapshot) -> str:
        if not snapshot.latest_available_trade_date:
            return ""
        warnings: list[str] = []
        if not snapshot.latest_trade_date:
            return f"最新 {snapshot.latest_available_trade_date} 的全量结果仍在重建，当前暂无可用榜单。"
        if snapshot.latest_trade_date < snapshot.latest_available_trade_date:
            warnings.append(
                f"当前使用 {snapshot.latest_trade_date} 的最近可用快照，"
                f"最新交易日 {snapshot.latest_available_trade_date} 的全量结果仍在重建或暂未完成。"
            )
        if snapshot.missing_strategies or snapshot.stale_strategies:
            warnings.append("部分策略结果仍在重建，榜单已自动合并最近可用快照。")
        return " ".join(warnings)

    def _get_priority_base_cache(self, cache_key: str) -> PriorityBaseSnapshot | None:
        return get_priority_base_cache(self, cache_key)

    def _set_priority_base_cache(self, cache_key: str, payload: PriorityBaseSnapshot) -> None:
        set_priority_base_cache(self, cache_key, payload)

    def _get_priority_response_cache(self, cache_key: str) -> LowBuyPriorityBoardResponse | None:
        return get_priority_response_cache(self, cache_key)

    def _set_priority_response_cache(self, cache_key: str, payload: LowBuyPriorityBoardResponse) -> None:
        set_priority_response_cache(self, cache_key, payload)

    def _load_watchlist_symbols(self, db: Session) -> set[str]:
        return set(db.execute(select(Watchlist.symbol)).scalars())

    def _collect_priority_candidates(
        self,
        db: Session,
        merged_candidates: dict[str, PriorityCandidate],
        tracked_symbols: set[str],
        latest_trade_date: str,
        candidates: list[LowBuyCandidateOut],
        performance_cache: dict[tuple[str, str, int], LowBuyStrategyPerformanceOut | None],
    ) -> None:
        collect_priority_candidates(
            builder=self,
            db=db,
            merged_candidates=merged_candidates,
            tracked_symbols=tracked_symbols,
            latest_trade_date=latest_trade_date,
            candidates=candidates,
            performance_cache=performance_cache,
        )

    def _upsert_strategy_hit(
        self,
        row: PriorityCandidate,
        hit: StrategyHit,
        strategy_key: str,
    ) -> None:
        upsert_strategy_hit(builder=self, row=row, hit=hit, strategy_key=strategy_key)

    def _build_strategy_hit(
        self,
        db: Session,
        candidate: LowBuyCandidateOut,
        latest_trade_date: str,
        performance_cache: dict[tuple[str, str, int], LowBuyStrategyPerformanceOut | None],
    ) -> StrategyHit:
        return build_strategy_hit(
            builder=self,
            db=db,
            candidate=candidate,
            latest_trade_date=latest_trade_date,
            performance_cache=performance_cache,
        )

    def _apply_priority_position_adjustment(
        self,
        candidate: LowBuyCandidateOut,
        performance: LowBuyStrategyPerformanceOut | None,
    ) -> LowBuyCandidateOut:
        if not hasattr(self, "_apply_candidate_positioning"):
            return candidate
        return self._apply_candidate_positioning(candidate, performance)

    def _load_cached_strategy_performance(
        self,
        db: Session,
        strategy_key: str,
        latest_trade_date: str,
        cache: dict[tuple[str, str, int], LowBuyStrategyPerformanceOut | None],
        lookback_days: int,
        build_if_missing: bool,
    ) -> LowBuyStrategyPerformanceOut | None:
        cache_key = (strategy_key, latest_trade_date, lookback_days)
        if cache_key not in cache:
            snapshot = self._load_strategy_performance_snapshot(
                db=db,
                strategy=strategy_key,
                latest_trade_date=latest_trade_date,
                lookback_days=lookback_days,
            )
            if snapshot is None and build_if_missing and latest_trade_date:
                if lookback_days == PERFORMANCE_LOOKBACK_DAYS:
                    snapshot = self._build_strategy_performance_snapshot(
                        db=db,
                        strategy=strategy_key,
                        latest_trade_date=latest_trade_date,
                    )
                else:
                    snapshot = self._ensure_recent_strategy_performance_snapshot(
                        db=db,
                        strategy=strategy_key,
                        latest_trade_date=latest_trade_date,
                    )
            cache[cache_key] = snapshot
        return cache[cache_key]

    def _refresh_priority_candidates(self, rows: list[PriorityCandidate]) -> list[PriorityCandidate]:
        return refresh_priority_candidates(builder=self, rows=rows)

    def _load_priority_intraday_bars(
        self,
        rows: list[PriorityCandidate],
        quote_map: dict[str, object],
        *,
        max_symbols: int = LOW_BUY_THRESHOLDS.MAX_SYMBOLS_QUOTE_REFRESH,
    ) -> dict[str, list]:
        return load_priority_intraday_bars(
            builder=self,
            rows=rows,
            quote_map=quote_map,
            max_symbols=max_symbols,
        )

    def _priority_needs_intraday_confirmation(self, row: PriorityCandidate, quote: object) -> bool:
        return priority_needs_intraday_confirmation(row, quote)

    def _priority_intraday_rank(self, row: PriorityCandidate, quote: object) -> tuple[int, float, float]:
        return priority_intraday_rank(builder=self, row=row, quote=quote)

    def _build_priority_items(
        self,
        rows: list[PriorityCandidate],
        market_context: PriorityMarketContext,
    ) -> list[LowBuyPriorityBoardItemOut]:
        return build_priority_items(
            rows=rows,
            market_context=market_context,
            builder=self,
        )

    def _attach_priority_recommendation_durations(
        self,
        *,
        db: Session,
        rows: list[PriorityCandidate],
        latest_trade_date: str,
    ) -> list[PriorityCandidate]:
        return attach_priority_recommendation_durations(
            db=db,
            rows=rows,
            latest_trade_date=latest_trade_date,
        )

    def _display_strategy_titles(self, hits: list[StrategyHit]) -> list[str]:
        return display_strategy_titles(builder=self, hits=hits)

    @staticmethod
    def _recommendation_days_by_title(hits: list[StrategyHit]) -> dict[str, int]:
        return recommendation_days_by_hit_title(hits)

    @staticmethod
    def _priority_recommendation_duration_text(
        *,
        candidate: LowBuyCandidateOut,
        recommendation_days_by_title: dict[str, int],
    ) -> str:
        return priority_recommendation_duration_text(
            candidate=candidate,
            recommendation_days_by_title=recommendation_days_by_title,
        )


    @staticmethod
    def _strategy_performance_text(performance: LowBuyStrategyPerformanceOut | None) -> str:
        return strategy_performance_text(performance)

    def _build_market_context(self, db: Session, latest_trade_date: str) -> PriorityMarketContext:
        return build_market_context(builder=self, db=db, latest_trade_date=latest_trade_date)

    def _primary_candidates_for_portfolio(
        self,
        rows: list[PriorityCandidate],
        market_context: PriorityMarketContext,
    ) -> list[LowBuyCandidateOut]:
        return select_primary_candidates_for_portfolio(
            rows=rows,
            market_context=market_context,
            selector=self,
        )


def filter_priority_candidates_for_recommendation(rows: list[PriorityCandidate]) -> list[PriorityCandidate]:
    """Keep recommendation boards aligned with current stock-scope policy."""

    return [row for row in rows if not is_growth_board_stock(row.symbol)]
