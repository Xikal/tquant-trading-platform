from __future__ import annotations

from copy import deepcopy
import json
import logging

from sqlalchemy import select

from app.core.config import get_settings
from app.models.entities import SystemSetting, Watchlist
from app.models.schemas import (
    LowBuyCandidateOut,
    LowBuyPriorityBoardItemOut,
    LowBuyPriorityBoardResponse,
    LowBuyStrategyPerformanceOut,
)
from app.services.latest_data_status import expected_low_buy_trade_date, published_low_buy_trade_date
from app.services.low_buy.main_force_model_shadow import summarize_main_force_shadow
from app.services.low_buy_materialization import enqueue_low_buy_materialization
from app.services.low_buy.priority_scoring import LowBuyPriorityScoringMixin
from app.services.low_buy.priority_cache import (
    get_priority_base_cache,
    get_priority_response_cache,
    priority_board_cache_epoch,
    set_priority_base_cache,
    set_priority_response_cache,
)
from app.services.low_buy.priority_board_read_model import (
    load_priority_board_read_model,
    priority_board_read_model_key,
    store_priority_board_read_model,
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
from app.services.low_buy.leader_strength_enrichment import enrich_priority_candidates_with_leader_strength
from app.services.low_buy.front_row_filter import (
    FrontRowFilterConfig,
    filter_priority_front_row_candidates,
    front_row_filter_warning,
)
from app.services.low_buy.front_row_readiness import front_row_readiness_summary
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
from app.services.low_buy.strategy_lanes import (
    FRONT_ROW_ONLY_VARIANT,
    FRONT_ROW_WEIGHTED_VARIANT,
    normalize_strategy_variant,
    project_items_to_lane,
)
from app.services.low_buy.shared import (
    LOW_BUY_THRESHOLDS,
    PERFORMANCE_LOOKBACK_DAYS,
    RECENT_PERFORMANCE_LOOKBACK_DAYS,
    Session,
)
from app.services.market.board_exclusions import is_growth_board_stock


logger = logging.getLogger(__name__)


class LowBuyPriorityBoardMixin(LowBuyPriorityScoringMixin):
    _main_force_shadow_summary_cache: dict | None = None

    def priority_board(
        self,
        db: Session,
        limit: int = 12,
        *,
        refresh_mode: str = "cache",
        front_row_only: bool = False,
        strategy_variant: str = "baseline",
    ) -> LowBuyPriorityBoardResponse:
        variant = normalize_strategy_variant(strategy_variant, front_row_only=front_row_only)
        target_trade_date = published_low_buy_trade_date(db) or expected_low_buy_trade_date(db)
        cache_epoch = priority_board_cache_epoch(target_trade_date)
        cache_key = f"date={target_trade_date}:limit={limit}:variant={variant}:epoch={cache_epoch}"
        normalized_refresh = str(refresh_mode or "cache").strip().lower()
        if normalized_refresh not in {"cache", "async", "sync"}:
            normalized_refresh = "cache"

        if normalized_refresh != "sync":
            cached_response = self._get_priority_response_cache(cache_key)
            if cached_response is not None:
                _log_priority_board_read_path("priority_board_response_cache", trade_date=target_trade_date)
                if normalized_refresh == "async":
                    _enqueue_priority_refresh(db, reason="priority_board_refresh_requested")
                    return _mark_priority_refresh_queued(cached_response, stale=False)
                return _mark_priority_read_path(cached_response, read_path="priority_board_response_cache")

            read_model_response = self._get_priority_read_model(
                cache_key=cache_key,
                target_trade_date=target_trade_date,
                strategy_variant=variant,
            )
            if read_model_response is not None:
                _log_priority_board_read_path("priority_board_read_model", trade_date=target_trade_date)
                if normalized_refresh == "async":
                    _enqueue_priority_refresh(db, reason="priority_board_read_model_refresh_requested")
                    return _mark_priority_refresh_queued(read_model_response, stale=False)
                return _mark_priority_read_path(read_model_response, read_path="priority_board_read_model")

            stale_response = self._get_priority_response_cache(cache_key, allow_stale=True)
            if stale_response is not None:
                _log_priority_board_read_path("priority_board_cached_background_refresh", trade_date=target_trade_date)
                _enqueue_priority_refresh(db, reason="priority_board_cache_miss")
                return _mark_priority_refresh_queued(stale_response, stale=True)

            _log_priority_board_read_path("priority_board_cache_empty", trade_date=target_trade_date)
            _enqueue_priority_refresh(db, reason="priority_board_cache_empty")
            if getattr(get_settings(), "priority_board_empty_fallback_to_last_snapshot", True):
                last_success = _load_latest_successful_priority_snapshot(db, variant=variant, limit=limit)
                if last_success is not None:
                    _log_priority_board_read_path("priority_board_latest_successful_snapshot", trade_date=target_trade_date)
                    return _mark_latest_successful_snapshot_queued(last_success)
            return _empty_priority_board_response(
                target_trade_date=target_trade_date,
                warning="优先榜正在后台刷新，当前暂无最近可用榜单。",
                strategy_variant=variant,
            )

        base_snapshot = self._load_priority_base_snapshot(db=db, limit=limit)
        self._main_force_shadow_summary_cache = summarize_main_force_shadow(db)
        try:
            refreshed_candidates = self._refresh_priority_candidates(base_snapshot.candidates)
            refreshed_candidates = self._attach_priority_recommendation_durations(
                db=db,
                rows=refreshed_candidates,
                latest_trade_date=base_snapshot.latest_trade_date,
            )
            refreshed_candidates = enrich_priority_candidates_with_leader_strength(db=db, rows=refreshed_candidates)
            front_row_warning = ""
            if variant == FRONT_ROW_ONLY_VARIANT:
                refreshed_candidates, front_row_stats = filter_priority_front_row_candidates(
                    refreshed_candidates,
                    FrontRowFilterConfig(enabled=True),
                )
                front_row_warning = front_row_filter_warning(front_row_stats)
            pre_policy_candidate_count = len(refreshed_candidates)
            refreshed_candidates = filter_priority_candidates_for_recommendation(refreshed_candidates)
            items = self._build_priority_items(
                refreshed_candidates,
                market_context=base_snapshot.market_context,
                strategy_variant=variant,
            )
            items = project_items_to_lane(items, variant)
            if variant == FRONT_ROW_WEIGHTED_VARIANT:
                items.sort(key=lambda item: (item.production_score or -1.0, item.priority_score), reverse=True)
            elif variant == FRONT_ROW_ONLY_VARIANT:
                items.sort(key=lambda item: (item.elite_watch_score or item.watch_score or -1.0, item.priority_score), reverse=True)
            else:
                items.sort(key=lambda item: item.priority_score, reverse=True)
            family_performance = build_family_performance(refreshed_candidates)
            family_sections = build_priority_family_sections(
                items=items,
                family_performance=family_performance,
            )
            snapshot_warning = self._priority_snapshot_warning(base_snapshot)
            if front_row_warning:
                snapshot_warning = f"{snapshot_warning} {front_row_warning}".strip()
            if pre_policy_candidate_count > 0 and not items:
                policy_warning = "当前候选均已被主板范围、风险或交易规则过滤，暂无可推荐股票。"
                snapshot_warning = f"{snapshot_warning} {policy_warning}".strip()
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
                strategy_variant=variant,
                readiness_summary=front_row_readiness_summary(variant),
            )
            self._set_priority_response_cache(cache_key, response)
            self._set_priority_read_model(
                cache_key=cache_key,
                target_trade_date=target_trade_date,
                strategy_variant=variant,
                payload=response,
            )
            _set_latest_successful_priority_snapshot(db, variant=variant, limit=limit, payload=response)
            return response
        finally:
            self._main_force_shadow_summary_cache = None

    def _main_force_shadow_status(self) -> dict:
        return self._main_force_shadow_summary_cache or {}

    def _load_priority_base_snapshot(self, db: Session, limit: int) -> PriorityBaseSnapshot:
        target_trade_date = published_low_buy_trade_date(db) or expected_low_buy_trade_date(db)
        cache_key = f"date={target_trade_date}:limit={limit}"
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

    def _get_priority_response_cache(
        self,
        cache_key: str,
        *,
        allow_stale: bool = False,
    ) -> LowBuyPriorityBoardResponse | None:
        return get_priority_response_cache(self, cache_key, allow_stale=allow_stale)

    def _set_priority_response_cache(self, cache_key: str, payload: LowBuyPriorityBoardResponse) -> None:
        set_priority_response_cache(self, cache_key, payload)

    def _get_priority_read_model(
        self,
        *,
        cache_key: str,
        target_trade_date: str,
        strategy_variant: str,
    ) -> LowBuyPriorityBoardResponse | None:
        settings = get_settings()
        if not getattr(settings, "priority_board_stable_read_model_enabled", True):
            return None
        payload = load_priority_board_read_model(
            _priority_read_model_key(
                cache_key=cache_key,
                target_trade_date=target_trade_date,
                strategy_variant=strategy_variant,
            )
        )
        if payload is None:
            return None
        try:
            return LowBuyPriorityBoardResponse.model_validate(payload)
        except Exception:
            return None

    def _set_priority_read_model(
        self,
        *,
        cache_key: str,
        target_trade_date: str,
        strategy_variant: str,
        payload: LowBuyPriorityBoardResponse,
    ) -> None:
        settings = get_settings()
        if not getattr(settings, "priority_board_stable_read_model_enabled", True):
            return
        store_priority_board_read_model(
            _priority_read_model_key(
                cache_key=cache_key,
                target_trade_date=target_trade_date,
                strategy_variant=strategy_variant,
            ),
            payload.model_copy(
                update={
                    "read_path": "priority_board_read_model",
                }
            ).model_dump(mode="json"),
            ttl_seconds=getattr(settings, "priority_board_stable_read_model_ttl_seconds", 45),
        )

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
        strategy_variant: str = "baseline",
    ) -> list[LowBuyPriorityBoardItemOut]:
        return build_priority_items(
            rows=rows,
            market_context=market_context,
            builder=self,
            strategy_variant=strategy_variant,
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


def _priority_read_model_key(
    *,
    cache_key: str,
    target_trade_date: str,
    strategy_variant: str,
) -> str:
    return priority_board_read_model_key(
        trade_date=target_trade_date,
        strategy_variant=strategy_variant,
        cache_key=cache_key,
    )


def _log_priority_board_read_path(read_path: str, *, trade_date: str) -> None:
    logger.info(
        "priority board read path selected",
        extra={"component": "priority-board", "read_path": read_path, "trade_date": trade_date},
    )


def _enqueue_priority_refresh(db: Session, *, reason: str) -> None:
    try:
        enqueue_low_buy_materialization(db, reason=reason, commit=False)
    except Exception:
        pass


def _mark_priority_refresh_queued(
    payload: LowBuyPriorityBoardResponse,
    *,
    stale: bool,
) -> LowBuyPriorityBoardResponse:
    effective_stale = stale or bool(payload.stale)
    warning = "优先榜正在后台刷新，当前先展示最近一次可用结果。"
    snapshot_warning = " ".join(part for part in [payload.snapshot_warning.strip(), warning] if part)
    tags = list(dict.fromkeys([*(payload.data_quality_tags or []), "refresh_queued"]))
    if effective_stale:
        tags = list(dict.fromkeys([*tags, "stale_cache"]))
    return payload.model_copy(
        update={
            "snapshot_warning": snapshot_warning,
            "data_quality": "stale" if effective_stale else payload.data_quality,
            "data_quality_text": "优先榜使用最近一次缓存，后台正在刷新。" if effective_stale else payload.data_quality_text,
            "data_quality_tags": tags,
            "stale": effective_stale,
            "stale_reason": payload.stale_reason
            or ("当前优先榜使用最近一次缓存，后台正在刷新；仅供复盘，不作为今日观察。" if effective_stale else ""),
            "refresh_queued": True,
            "read_path": payload.read_path or "priority_board_cached_background_refresh",
        }
    )


def _mark_latest_successful_snapshot_queued(payload: LowBuyPriorityBoardResponse) -> LowBuyPriorityBoardResponse:
    warning = "优先榜正在后台刷新，当前展示上次可用榜单。"
    snapshot_warning = " ".join(part for part in [payload.snapshot_warning.strip(), warning] if part)
    tags = list(dict.fromkeys([*(payload.data_quality_tags or []), "refresh_queued", "stale_snapshot"]))
    return payload.model_copy(
        update={
            "snapshot_warning": snapshot_warning,
            "data_quality": "stale",
            "data_quality_text": "优先榜正在后台刷新，当前展示上次可用榜单。",
            "data_quality_tags": tags,
            "stale": True,
            "stale_reason": "优先榜正在后台刷新，当前展示上次可用榜单；仅供复盘，不作为今日观察。",
            "refresh_queued": True,
            "read_path": payload.read_path or "priority_board_latest_successful_snapshot",
        }
    )


def _mark_priority_read_path(payload: LowBuyPriorityBoardResponse, *, read_path: str) -> LowBuyPriorityBoardResponse:
    return payload.model_copy(
        update={
            "read_path": read_path,
            "stale": bool(payload.stale),
            "refresh_queued": bool(payload.refresh_queued),
        }
    )


def _empty_priority_board_response(
    *,
    target_trade_date: str,
    warning: str,
    strategy_variant: str = "baseline",
) -> LowBuyPriorityBoardResponse:
    from app.core.timezone import beijing_now_string
    from app.services.low_buy.front_row_readiness import front_row_readiness_summary
    from app.services.low_buy.strategy_lanes import available_lane_payloads, lane_summary, resolve_strategy_lane

    lane = resolve_strategy_lane(strategy_variant)
    return LowBuyPriorityBoardResponse(
        strategy_variant=lane.variant,
        display_lane=lane.display_lane,
        display_lane_title=lane.title,
        display_lane_subtitle=lane.subtitle,
        production_sort_replaced=lane.production_sort_replaced,
        lane_summary=lane_summary(lane.variant, []),
        available_lanes=available_lane_payloads(),
        readiness_summary=front_row_readiness_summary(lane.variant),
        as_of_date=target_trade_date,
        latest_trade_date="",
        latest_available_trade_date=target_trade_date,
        updated_at=beijing_now_string(),
        total_candidates=0,
        snapshot_warning=warning,
        data_quality="unavailable",
        data_quality_text="优先榜后台刷新中，暂无可用快照。",
        data_quality_tags=["refresh_queued", "cache_empty"],
        stale=True,
        stale_reason="优先榜正在后台刷新，当前暂无可用榜单；请等待最新交易日快照生成。",
        refresh_queued=True,
        read_path="priority_board_empty_background_refresh",
        items=[],
        family_sections=[],
        simple_buckets=[],
    )


def _latest_priority_snapshot_key(*, variant: str, limit: int) -> str:
    return f"priority_board:last:{variant}:{int(limit)}"


def _set_latest_successful_priority_snapshot(
    db: Session,
    *,
    variant: str,
    limit: int,
    payload: LowBuyPriorityBoardResponse,
) -> None:
    try:
        key = _latest_priority_snapshot_key(variant=variant, limit=limit)
        value = payload.model_dump_json()
        row = db.execute(select(SystemSetting).where(SystemSetting.key == key)).scalar_one_or_none()
        if row is None:
            db.add(SystemSetting(key=key, value=value))
        else:
            row.value = value
        if hasattr(db, "commit"):
            db.commit()
    except Exception:
        if hasattr(db, "rollback"):
            db.rollback()


def _load_latest_successful_priority_snapshot(
    db: Session,
    *,
    variant: str,
    limit: int,
) -> LowBuyPriorityBoardResponse | None:
    try:
        row = db.execute(
            select(SystemSetting.value).where(
                SystemSetting.key == _latest_priority_snapshot_key(variant=variant, limit=limit)
            )
        ).scalar_one_or_none()
        if not row:
            return None
        return LowBuyPriorityBoardResponse.model_validate(json.loads(str(row)))
    except Exception:
        return None
