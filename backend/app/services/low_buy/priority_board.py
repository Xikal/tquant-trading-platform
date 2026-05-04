from __future__ import annotations

from copy import deepcopy
import time

from sqlalchemy import select

from app.models.entities import Watchlist
from app.models.schemas import (
    LowBuyCandidateOut,
    LowBuyPriorityFamilyPerformanceOut,
    LowBuyPriorityFamilySectionOut,
    LowBuyPriorityBoardItemOut,
    LowBuyPriorityBoardResponse,
    LowBuyStrategyPerformanceOut,
)
from app.repositories.low_buy.results import LowBuyResultRepository
from app.repositories.low_buy.lifecycle import LowBuyTradeLifecycleRepository
from app.services.low_buy.priority_scoring import LowBuyPriorityScoringMixin
from app.services.low_buy.market_state_rules import compute_directional_bias, directional_bias_text
from app.services.low_buy.data_quality import build_market_data_quality, data_quality_payload
from app.services.low_buy.portfolio_risk import build_lifecycle_holdings, build_portfolio_risk
from app.services.low_buy.priority_types import (
    PriorityBaseSnapshot,
    PriorityCandidate,
    PriorityMarketContext,
    StrategyHit,
)
from app.services.low_buy.shared import (
    LOW_BUY_THRESHOLDS,
    PERFORMANCE_LOOKBACK_DAYS,
    PLAYBOOKS,
    RECENT_PERFORMANCE_LOOKBACK_DAYS,
    Session,
    datetime,
)
from app.services.low_buy.strategy_policy import participates_in_priority_board
from app.services.low_buy.strategy_families import resolve_strategy_family, resolve_strategy_family_label
from app.services.low_buy.recommendation_duration import attach_recommendation_durations
from app.services.low_buy.simple_decision import build_daily_decision, build_simple_buckets, enrich_priority_items
from app.services.market.state_categories import standard_market_state_payload


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
        items = self._build_priority_items(
            refreshed_candidates,
            market_context=base_snapshot.market_context,
        )
        items.sort(key=lambda item: item.priority_score, reverse=True)
        family_performance = self._build_family_performance(refreshed_candidates)
        family_sections = self._build_priority_family_sections(
            items=items,
            family_performance=family_performance,
        )
        portfolio_candidates = self._primary_candidates_for_portfolio(
            refreshed_candidates,
            market_context=base_snapshot.market_context,
        )
        directional_bias = compute_directional_bias(
            base_snapshot.market_context.market_state,
            regime_scores={"style_divergence": base_snapshot.market_context.style_divergence},
            emotion_data={
                "broken_board_ratio": base_snapshot.market_context.broken_board_ratio,
                "limit_down_count": base_snapshot.market_context.limit_down_count or 0,
                "limit_up_count": base_snapshot.market_context.limit_up_count,
            },
            mainline_strength={"strength": base_snapshot.market_context.market_state_strength},
        )
        snapshot_warning = self._priority_snapshot_warning(base_snapshot)
        market_state_fields = standard_market_state_payload(base_snapshot.market_context.market_state)
        quality_fields = data_quality_payload(
            build_market_data_quality(
                breadth_ready=base_snapshot.market_context.breadth_ready,
                emotion_ready=base_snapshot.market_context.emotion_ready,
                hot_industry_source=base_snapshot.market_context.hot_industry_source,
                snapshot_warning=snapshot_warning,
            )
        )

        response = LowBuyPriorityBoardResponse(
            as_of_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            latest_trade_date=base_snapshot.latest_trade_date,
            latest_available_trade_date=base_snapshot.latest_available_trade_date,
            snapshot_warning=snapshot_warning,
            updated_at=base_snapshot.updated_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            total_candidates=len(items),
            immediate_count=sum(item.buy_signal_state in {"buy_now", "soft_buy_now"} for item in items),
            focus_count=sum(item.buy_signal_state == "near_entry" for item in items),
            track_count=sum(item.buy_signal_state == "watch" for item in items),
            market_state=base_snapshot.market_context.market_state,
            market_state_text=self._market_state_text(base_snapshot.market_context),
            market_state_category=market_state_fields["market_state_category"],
            market_state_category_text=market_state_fields["market_state_category_text"],
            **quality_fields,
            directional_bias=directional_bias,
            directional_bias_text=directional_bias_text(directional_bias),
            market_bonus=base_snapshot.market_context.market_bonus,
            market_state_strength=base_snapshot.market_context.market_state_strength,
            regime_confidence=base_snapshot.market_context.regime_confidence,
            state_persistence_days=base_snapshot.market_context.state_persistence_days,
            transition_risk=base_snapshot.market_context.transition_risk,
            breadth_ready=base_snapshot.market_context.breadth_ready,
            emotion_ready=base_snapshot.market_context.emotion_ready,
            stock_up_ratio=base_snapshot.market_context.stock_up_ratio,
            stock_median_change=base_snapshot.market_context.stock_median_change,
            style_divergence=base_snapshot.market_context.style_divergence,
            hot_turnover=base_snapshot.market_context.hot_turnover,
            hot_overlap_ratio=base_snapshot.market_context.hot_overlap_ratio,
            limit_down_count=base_snapshot.market_context.limit_down_count,
            limit_up_count=base_snapshot.market_context.limit_up_count,
            board_height=base_snapshot.market_context.board_height,
            previous_board_height=base_snapshot.market_context.previous_board_height,
            promotion_ratio=base_snapshot.market_context.promotion_ratio,
            broken_board_ratio=base_snapshot.market_context.broken_board_ratio,
            promotion_break_gap=base_snapshot.market_context.promotion_break_gap,
            promotion_break_pressure=base_snapshot.market_context.promotion_break_pressure,
            high_flyer_retreat_ratio=base_snapshot.market_context.high_flyer_retreat_ratio,
            high_flyer_gap_speed=base_snapshot.market_context.high_flyer_gap_speed,
            distribution_pressure=base_snapshot.market_context.distribution_pressure,
            hot_industries=base_snapshot.market_context.hot_industries,
            hot_industry_source=base_snapshot.market_context.hot_industry_source,
            hot_industry_source_text=base_snapshot.market_context.hot_industry_source_text,
            mainline_lifecycle_state=base_snapshot.market_context.mainline_lifecycle_state,
            mainline_lifecycle_text=base_snapshot.market_context.mainline_lifecycle_text,
            portfolio_risk=build_portfolio_risk(
                portfolio_candidates,
                market_state=base_snapshot.market_context.market_state,
                active_holdings=build_lifecycle_holdings(
                    LowBuyTradeLifecycleRepository(db).fetch_active(limit=300)
                ),
            ),
            missing_strategies=base_snapshot.missing_strategies,
            stale_strategies=base_snapshot.stale_strategies,
            family_sections=family_sections,
            items=items[:limit],
        )
        response.items = enrich_priority_items(response.items)
        response.daily_decision = build_daily_decision(response)
        response.simple_buckets = build_simple_buckets(response.items)
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
        latest_available_trade_date = LowBuyResultRepository(db).fetch_latest_trade_date() or ""
        tracked_symbols = self._load_watchlist_symbols(db)
        merged_candidates: dict[str, PriorityCandidate] = {}
        performance_cache: dict[tuple[str, str, int], LowBuyStrategyPerformanceOut | None] = {}
        latest_trade_date = ""
        updated_at = ""
        missing_strategies: list[str] = []
        stale_strategies: list[str] = []

        for strategy_key in PLAYBOOKS:
            if not participates_in_priority_board(strategy_key):
                continue
            payload = self._load_latest_materialized_full_result(
                db=db,
                strategy=strategy_key,
                limit=max(limit * 2, 24),
                include_history=False,
                allow_repair=False,
            )
            if payload is None:
                missing_strategies.append(strategy_key)
                continue
            if latest_available_trade_date and payload.latest_trade_date < latest_available_trade_date:
                stale_strategies.append(strategy_key)
            latest_trade_date = max(latest_trade_date, payload.latest_trade_date)
            updated_at = max(updated_at, payload.full_scan_updated_at or payload.as_of_date)
            self._collect_priority_candidates(
                db=db,
                merged_candidates=merged_candidates,
                tracked_symbols=tracked_symbols,
                latest_trade_date=payload.latest_trade_date,
                candidates=payload.confirmed_candidates + payload.candidates,
                performance_cache=performance_cache,
            )

        market_context = self._build_market_context(db=db, latest_trade_date=latest_trade_date)
        return PriorityBaseSnapshot(
            latest_trade_date=latest_trade_date,
            latest_available_trade_date=latest_available_trade_date,
            updated_at=updated_at,
            candidates=list(merged_candidates.values()),
            market_context=market_context,
            missing_strategies=missing_strategies,
            stale_strategies=stale_strategies,
        )

    @staticmethod
    def _priority_snapshot_warning(snapshot: PriorityBaseSnapshot) -> str:
        if not snapshot.latest_available_trade_date:
            return ""
        warnings: list[str] = []
        if not snapshot.latest_trade_date:
            return f"最新 {snapshot.latest_available_trade_date} 的全量结果仍在重建，当前暂无可用榜单。"
        if snapshot.latest_trade_date < snapshot.latest_available_trade_date:
            warnings.append(
                f"当前使用 {snapshot.latest_trade_date} 的回退快照，"
                f"最新 {snapshot.latest_available_trade_date} 的结果仍在重建或暂未纳入。"
            )
        if snapshot.missing_strategies:
            warnings.append(f"缺失策略：{', '.join(snapshot.missing_strategies)}。")
        if snapshot.stale_strategies:
            warnings.append(f"过期策略：{', '.join(snapshot.stale_strategies)}。")
        return " ".join(warnings)

    def _get_priority_base_cache(self, cache_key: str) -> PriorityBaseSnapshot | None:
        now = time.monotonic()
        with self._cache_lock:
            cached = self._priority_base_cache.get(cache_key)
            if cached is None:
                return None
            expires_at, payload = cached
            if expires_at <= now:
                self._priority_base_cache.pop(cache_key, None)
                return None
            return deepcopy(payload)

    def _set_priority_base_cache(self, cache_key: str, payload: PriorityBaseSnapshot) -> None:
        with self._cache_lock:
            self._priority_base_cache[cache_key] = (
                time.monotonic() + self._priority_base_cache_ttl,
                deepcopy(payload),
            )

    def _get_priority_response_cache(self, cache_key: str) -> LowBuyPriorityBoardResponse | None:
        now = time.monotonic()
        with self._cache_lock:
            cached = self._priority_response_cache.get(cache_key)
            if cached is None:
                return None
            expires_at, payload = cached
            if expires_at <= now:
                self._priority_response_cache.pop(cache_key, None)
                return None
            return deepcopy(payload)

    def _set_priority_response_cache(self, cache_key: str, payload: LowBuyPriorityBoardResponse) -> None:
        with self._cache_lock:
            self._priority_response_cache[cache_key] = (
                time.monotonic() + self._priority_response_cache_ttl,
                deepcopy(payload),
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
        for candidate in candidates:
            if candidate.symbol in tracked_symbols or candidate.buy_signal_state == "avoid":
                continue
            strategy_key = candidate.strategy_key
            row = merged_candidates.setdefault(candidate.symbol, PriorityCandidate(symbol=candidate.symbol))
            hit = self._build_strategy_hit(
                db=db,
                candidate=candidate,
                latest_trade_date=latest_trade_date,
                performance_cache=performance_cache,
            )
            self._upsert_strategy_hit(row=row, hit=hit, strategy_key=strategy_key)

    def _upsert_strategy_hit(
        self,
        row: PriorityCandidate,
        hit: StrategyHit,
        strategy_key: str,
    ) -> None:
        for index, existing in enumerate(row.hits):
            if existing.strategy_key != strategy_key:
                continue
            if self._single_strategy_rank(hit.candidate, hit.strategy_weight_score + hit.context_bonus) > self._single_strategy_rank(
                existing.candidate,
                existing.strategy_weight_score + existing.context_bonus,
            ):
                row.hits[index] = hit
            return
        row.hits.append(hit)

    def _build_strategy_hit(
        self,
        db: Session,
        candidate: LowBuyCandidateOut,
        latest_trade_date: str,
        performance_cache: dict[tuple[str, str, int], LowBuyStrategyPerformanceOut | None],
    ) -> StrategyHit:
        base_performance = self._load_cached_strategy_performance(
            db=db,
            strategy_key=candidate.strategy_key,
            latest_trade_date=latest_trade_date,
            cache=performance_cache,
            lookback_days=PERFORMANCE_LOOKBACK_DAYS,
            build_if_missing=False,
        )
        recent_performance = self._load_cached_strategy_performance(
            db=db,
            strategy_key=candidate.strategy_key,
            latest_trade_date=latest_trade_date,
            cache=performance_cache,
            lookback_days=RECENT_PERFORMANCE_LOOKBACK_DAYS,
            build_if_missing=False,
        )
        strategy_weight_score = self._strategy_weight_score(base_performance, recent_performance)
        context_bonus = self._strategy_context_bonus(candidate, base_performance, recent_performance)
        adjusted_candidate = self._apply_priority_position_adjustment(
            candidate,
            base_performance,
        )
        return StrategyHit(
            strategy_key=candidate.strategy_key,
            strategy_title=candidate.strategy_title,
            family_key=resolve_strategy_family(candidate.strategy_key),
            candidate=adjusted_candidate,
            strategy_weight_score=strategy_weight_score,
            context_bonus=context_bonus,
            performance=base_performance,
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
        symbols = [row.symbol for row in rows]
        quote_map = self.market_data.get_quotes_batch(
            symbols,
            force_refresh=False,
            allow_slow_fallback=False,
        )
        intraday_bars_by_symbol = self._load_priority_intraday_bars(rows, quote_map)
        refreshed_rows: list[PriorityCandidate] = []
        for row in rows:
            quote = quote_map.get(row.symbol)
            if not quote:
                refreshed_rows.append(row)
                continue
            refreshed_hits = [
                StrategyHit(
                    strategy_key=hit.strategy_key,
                    strategy_title=hit.strategy_title,
                    family_key=hit.family_key,
                    candidate=self._refresh_buy_signal(
                        hit.candidate,
                        quote=quote,
                        intraday_bars=intraday_bars_by_symbol.get(row.symbol),
                        require_intraday_structure=True,
                    ),
                    strategy_weight_score=hit.strategy_weight_score,
                    context_bonus=hit.context_bonus,
                    performance=hit.performance,
                )
                for hit in row.hits
            ]
            refreshed_rows.append(PriorityCandidate(symbol=row.symbol, hits=refreshed_hits))
        return refreshed_rows

    def _load_priority_intraday_bars(
        self,
        rows: list[PriorityCandidate],
        quote_map: dict[str, object],
        *,
        max_symbols: int = LOW_BUY_THRESHOLDS.MAX_SYMBOLS_QUOTE_REFRESH,
    ) -> dict[str, list]:
        ranked_symbols: list[tuple[tuple[int, float, float], str]] = []
        for row in rows:
            quote = quote_map.get(row.symbol)
            if quote is None or not self._priority_needs_intraday_confirmation(row, quote):
                continue
            ranked_symbols.append((self._priority_intraday_rank(row, quote), row.symbol))
        ranked_symbols.sort()
        eligible_symbols = [symbol for _, symbol in ranked_symbols[:max_symbols]]
        return self.market_data.get_intraday_bars_batch(
            symbols=eligible_symbols,
            period="1m",
            limit=30,
            max_workers=8,
        )

    def _priority_needs_intraday_confirmation(self, row: PriorityCandidate, quote: object) -> bool:
        latest_price = float(getattr(quote, "last_price", 0.0) or 0.0)
        if latest_price <= 0:
            return False
        for hit in row.hits:
            candidate = hit.candidate
            if latest_price <= candidate.stop_loss * 1.003:
                continue
            if latest_price <= candidate.entry_zone_high * 1.012:
                return True
        return False

    def _priority_intraday_rank(self, row: PriorityCandidate, quote: object) -> tuple[int, float, float]:
        latest_price = float(getattr(quote, "last_price", 0.0) or 0.0)
        best_state_rank = 9
        best_distance = 99.0
        best_score = 0.0
        state_rank = {"buy_now": 0, "soft_buy_now": 1, "near_entry": 2, "watch": 3}
        for hit in row.hits:
            candidate = hit.candidate
            best_state_rank = min(best_state_rank, state_rank.get(candidate.buy_signal_state, 4))
            distance = self._distance_to_entry_zone_pct(candidate, latest_price)
            best_distance = min(best_distance, distance)
            best_score = max(best_score, float(candidate.score or 0.0))
        return (best_state_rank, best_distance, -best_score)

    def _build_priority_items(
        self,
        rows: list[PriorityCandidate],
        market_context: PriorityMarketContext,
    ) -> list[LowBuyPriorityBoardItemOut]:
        items: list[LowBuyPriorityBoardItemOut] = []
        for row in rows:
            if not row.hits:
                continue
            aggregate_weight = self._aggregate_strategy_weight(row.hits)
            strategy_count = self._effective_strategy_count(row.hits)
            family_count = self._effective_family_count(row.hits)
            primary_hit = max(
                row.hits,
                key=lambda hit: self._final_rank_score(
                    candidate=hit.candidate,
                    aggregate_weight=aggregate_weight,
                    family_count=family_count,
                    strategy_weight=hit.strategy_weight_score + hit.context_bonus,
                    market_context=market_context,
                ),
            )
            candidate = primary_hit.candidate
            strategy_titles = self._display_strategy_titles(row.hits)
            recommendation_days_by_title = self._recommendation_days_by_title(row.hits)
            recommendation_days = max(recommendation_days_by_title.values(), default=candidate.recommendation_days)
            industry_rotation_bonus = self._sector_rotation_bonus(candidate, market_context)
            items.append(
                LowBuyPriorityBoardItemOut(
                    symbol=candidate.symbol,
                    name=candidate.name,
                    sector_name=candidate.sector_name,
                    strategy_key=primary_hit.strategy_key,
                    strategy_title=primary_hit.strategy_title,
                    strategy_titles=strategy_titles,
                    strategy_count=strategy_count,
                    family_count=family_count,
                    strategy_family=primary_hit.family_key,
                    strategy_family_text=resolve_strategy_family_label(primary_hit.strategy_key),
                    latest_price=candidate.latest_price,
                    change_pct=candidate.change_pct,
                    quote_timestamp=candidate.quote_timestamp,
                    data_quality=candidate.data_quality,
                    data_quality_text=candidate.data_quality_text,
                    data_quality_tags=candidate.data_quality_tags,
                    market_state_category=candidate.market_state_category,
                    market_state_category_text=candidate.market_state_category_text,
                    buy_signal_state=candidate.buy_signal_state,
                    buy_signal_text=candidate.buy_signal_text,
                    priority_score=self._final_rank_score(
                        candidate=candidate,
                        aggregate_weight=aggregate_weight,
                        family_count=family_count,
                        strategy_weight=primary_hit.strategy_weight_score + primary_hit.context_bonus,
                        market_context=market_context,
                    ),
                    strategy_weight_score=round(aggregate_weight, 2),
                    industry_rotation_bonus=industry_rotation_bonus,
                    industry_rotation_text=self._industry_rotation_text(candidate, market_context, industry_rotation_bonus),
                    industry_tier=candidate.industry_tier,
                    industry_tier_text=candidate.industry_tier_text,
                    industry_position_multiplier=candidate.industry_position_multiplier,
                    position_breakdown_text=candidate.position_breakdown_text,
                    action_summary=self._priority_action_summary(candidate),
                    blocked_reason=self._priority_blocked_reason(candidate),
                    trigger_condition=candidate.trigger_condition,
                    invalid_condition=candidate.invalid_condition,
                    risk_tier=candidate.risk_tier,
                    next_watch_price=candidate.next_watch_price,
                    leader_rank=candidate.leader_rank,
                    mainline_rank=candidate.mainline_rank,
                    mainline_tier=candidate.mainline_tier,
                    mainline_tier_text=candidate.mainline_tier_text,
                    execution_quality_score=candidate.execution_quality_score,
                    execution_quality_text=candidate.execution_quality_text,
                    strategy_performance_text=self._strategy_performance_text(primary_hit.performance),
                    next_day_event_plan=candidate.next_day_event_plan,
                    entry_zone_low=candidate.entry_zone_low,
                    entry_zone_high=candidate.entry_zone_high,
                    stop_loss=candidate.stop_loss,
                    suggested_position_pct=candidate.suggested_position_pct,
                    suggested_position_text=candidate.suggested_position_text,
                    recommendation_start_date=candidate.recommendation_start_date,
                    recommendation_days=recommendation_days,
                    strategy_recommendation_days=recommendation_days_by_title,
                    recommendation_duration_text=self._priority_recommendation_duration_text(
                        candidate=candidate,
                        recommendation_days_by_title=recommendation_days_by_title,
                    ),
                )
            )
        return items

    def _attach_priority_recommendation_durations(
        self,
        *,
        db: Session,
        rows: list[PriorityCandidate],
        latest_trade_date: str,
    ) -> list[PriorityCandidate]:
        candidates = [hit.candidate for row in rows for hit in row.hits]
        enriched = attach_recommendation_durations(
            db=db,
            candidates=candidates,
            latest_trade_date=latest_trade_date,
        )
        enriched_by_key = {(candidate.strategy_key, candidate.symbol): candidate for candidate in enriched}
        result: list[PriorityCandidate] = []
        for row in rows:
            result.append(
                PriorityCandidate(
                    symbol=row.symbol,
                    hits=[
                        StrategyHit(
                            strategy_key=hit.strategy_key,
                            strategy_title=hit.strategy_title,
                            family_key=hit.family_key,
                            candidate=enriched_by_key.get((hit.strategy_key, hit.candidate.symbol), hit.candidate),
                            strategy_weight_score=hit.strategy_weight_score,
                            context_bonus=hit.context_bonus,
                            performance=hit.performance,
                        )
                        for hit in row.hits
                    ],
                )
            )
        return result

    @staticmethod
    def _recommendation_days_by_title(hits: list[StrategyHit]) -> dict[str, int]:
        result: dict[str, int] = {}
        for hit in hits:
            days = int(hit.candidate.recommendation_days or 0)
            if days <= 0:
                continue
            title = hit.strategy_title or hit.strategy_key
            result[title] = max(result.get(title, 0), days)
        return result

    @staticmethod
    def _priority_recommendation_duration_text(
        *,
        candidate: LowBuyCandidateOut,
        recommendation_days_by_title: dict[str, int],
    ) -> str:
        if not recommendation_days_by_title:
            return candidate.recommendation_duration_text
        title, max_recommendation_days = max(
            recommendation_days_by_title.items(),
            key=lambda pair: pair[1],
        )
        max_holding_days = max(int(candidate.exit_plan.max_holding_days or 0), 1)
        if max_recommendation_days >= max_holding_days:
            return f"{title}第 {max_recommendation_days} 天，已达到建议验证窗口 {max_holding_days} 天；未转强应降级或退出。"
        return f"{title}第 {max_recommendation_days} 天，建议验证窗口 {max_holding_days} 天；剩余 {max_holding_days - max_recommendation_days} 天。"

    @staticmethod
    def _strategy_performance_text(performance: LowBuyStrategyPerformanceOut | None) -> str:
        if performance is None:
            return "策略表现：暂无可用绩效样本，先按结构和风控判断。"
        filled = int(performance.filled_signals or 0)
        if filled < 5:
            return f"策略表现：近 {performance.lookback_days} 日真实成交样本 {filled} 个，样本不足。"
        return (
            f"策略表现：近 {performance.lookback_days} 日盈利率 {performance.hit_rate:.1f}%、"
            f"净胜优势 {performance.net_win_rate:+.1f}%、"
            f"均收 {performance.avg_net_return_pct:+.2f}%、未成交 {performance.not_filled_rate:.1f}%"
        )

    def _display_strategy_titles(self, hits: list[StrategyHit]) -> list[str]:
        titles_by_family: dict[str, str] = {}
        for hit in self._ordered_hits_for_aggregation(hits):
            family_key = hit.family_key or hit.strategy_key
            if family_key in titles_by_family:
                continue
            titles_by_family[family_key] = hit.strategy_title
        return list(titles_by_family.values())

    def _build_priority_family_sections(
        self,
        *,
        items: list[LowBuyPriorityBoardItemOut],
        family_performance: dict[str, LowBuyPriorityFamilyPerformanceOut],
        limit_per_family: int = 6,
    ) -> list[LowBuyPriorityFamilySectionOut]:
        grouped: dict[str, list[LowBuyPriorityBoardItemOut]] = {}
        for item in items:
            grouped.setdefault(item.strategy_family or "uncategorized", []).append(item)
        sections: list[LowBuyPriorityFamilySectionOut] = []
        for family_key, family_items in grouped.items():
            ordered = sorted(family_items, key=lambda item: item.priority_score, reverse=True)
            family_text = ordered[0].strategy_family_text if ordered else resolve_strategy_family_label(family_key)
            sections.append(
                LowBuyPriorityFamilySectionOut(
                    family_key=family_key,
                    family_text=family_text,
                    total_candidates=len(ordered),
                    immediate_count=sum(item.buy_signal_state in {"buy_now", "soft_buy_now"} for item in ordered),
                    focus_count=sum(item.buy_signal_state == "near_entry" for item in ordered),
                    track_count=sum(item.buy_signal_state == "watch" for item in ordered),
                    avg_priority_score=round(sum(item.priority_score for item in ordered) / max(len(ordered), 1), 2),
                    top_strategy_titles=self._unique_strategy_titles_from_items(ordered),
                    performance=family_performance.get(family_key),
                    items=ordered[:limit_per_family],
                )
            )
        sections.sort(
            key=lambda section: (
                section.immediate_count,
                section.focus_count,
                section.avg_priority_score,
                section.total_candidates,
            ),
            reverse=True,
        )
        return sections

    @staticmethod
    def _unique_strategy_titles_from_items(items: list[LowBuyPriorityBoardItemOut]) -> list[str]:
        titles: list[str] = []
        for item in items:
            for title in item.strategy_titles or [item.strategy_title]:
                if title not in titles:
                    titles.append(title)
        return titles[:4]

    def _build_family_performance(
        self,
        rows: list[PriorityCandidate],
    ) -> dict[str, LowBuyPriorityFamilyPerformanceOut]:
        accumulators: dict[str, dict[str, float | int | str | set[str]]] = {}
        seen: set[tuple[str, str]] = set()
        for row in rows:
            for hit in row.hits:
                if hit.performance is None:
                    continue
                family_key = hit.family_key or resolve_strategy_family(hit.strategy_key)
                strategy_key = hit.strategy_key
                if (family_key, strategy_key) in seen:
                    continue
                seen.add((family_key, strategy_key))
                bucket = accumulators.setdefault(
                    family_key,
                    {
                        "family_text": resolve_strategy_family_label(strategy_key),
                        "strategies": set(),
                        "evaluated_signals": 0,
                        "filled_signals": 0,
                        "not_filled_signals": 0,
                        "hit_count": 0,
                        "net_win_rate_sum": 0.0,
                        "net_return_sum": 0.0,
                        "not_filled_count": 0.0,
                        "stop_loss_count": 0.0,
                    },
                )
                performance = hit.performance
                evaluated = int(performance.evaluated_signals or 0)
                filled = int(performance.filled_signals or 0)
                not_filled = int(performance.not_filled_signals or 0)
                hit_count = int(performance.hit_count or 0)
                bucket["strategies"].add(strategy_key)  # type: ignore[union-attr]
                bucket["evaluated_signals"] = int(bucket["evaluated_signals"]) + evaluated
                bucket["filled_signals"] = int(bucket["filled_signals"]) + filled
                bucket["not_filled_signals"] = int(bucket["not_filled_signals"]) + not_filled
                bucket["hit_count"] = int(bucket["hit_count"]) + hit_count
                bucket["net_win_rate_sum"] = float(bucket["net_win_rate_sum"]) + performance.net_win_rate * filled
                bucket["net_return_sum"] = float(bucket["net_return_sum"]) + performance.avg_net_return_pct * filled
                bucket["not_filled_count"] = float(bucket["not_filled_count"]) + not_filled
                bucket["stop_loss_count"] = float(bucket["stop_loss_count"]) + performance.stop_loss_rate / 100 * filled
        return {
            family_key: self._family_performance_from_bucket(family_key, bucket)
            for family_key, bucket in accumulators.items()
        }

    @staticmethod
    def _family_performance_from_bucket(
        family_key: str,
        bucket: dict[str, float | int | str | set[str]],
    ) -> LowBuyPriorityFamilyPerformanceOut:
        evaluated = int(bucket["evaluated_signals"])
        filled = int(bucket["filled_signals"])
        hit_count = int(bucket["hit_count"])
        not_filled = int(bucket["not_filled_signals"])
        strategies = bucket["strategies"]
        strategy_count = len(strategies) if isinstance(strategies, set) else 0
        return LowBuyPriorityFamilyPerformanceOut(
            family_key=family_key,
            family_text=str(bucket["family_text"]),
            strategy_count=strategy_count,
            evaluated_signals=evaluated,
            filled_signals=filled,
            not_filled_signals=not_filled,
            hit_count=hit_count,
            net_win_rate=round(float(bucket["net_win_rate_sum"]) / max(filled, 1), 2),
            avg_net_return_pct=round(float(bucket["net_return_sum"]) / max(filled, 1), 2),
            not_filled_rate=round(not_filled / max(evaluated, 1) * 100, 2),
            stop_loss_rate=round(float(bucket["stop_loss_count"]) / max(filled, 1) * 100, 2),
            hit_rate=round(hit_count / max(filled, 1) * 100, 2),
        )

    def _build_market_context(self, db: Session, latest_trade_date: str) -> PriorityMarketContext:
        persisted_pool = self._load_persisted_pool(db=db, latest_trade_date=latest_trade_date) or {}
        if not latest_trade_date and not persisted_pool:
            return PriorityMarketContext(
                market_state="low_volume_wait",
                market_bonus=0.0,
                market_state_label="缩量无主线",
                market_state_description="当前还没有可用样本，先按中性偏防守环境处理。",
                regime_confidence=0.0,
                state_persistence_days=1,
                transition_risk=0.0,
                breadth_ready=False,
                emotion_ready=False,
                stock_up_ratio=0.0,
                stock_median_change=0.0,
                style_divergence=0.0,
                hot_turnover=0.0,
                hot_overlap_ratio=0.0,
                limit_down_count=None,
                limit_up_count=0,
                board_height=0,
                previous_board_height=0,
                promotion_ratio=0.0,
                broken_board_ratio=0.0,
                promotion_break_gap=0.0,
                promotion_break_pressure=0.0,
                high_flyer_retreat_ratio=0.0,
                high_flyer_gap_speed=0.0,
                distribution_pressure=0.0,
                hot_industries=[],
                hot_industry_source="unavailable",
                hot_industry_source_text="热点来源：暂无有效归因",
                mainline_lifecycle_state="unknown",
                mainline_lifecycle_text="主线阶段：热点归因不足",
                industry_ranks={},
                market_state_strength=0.0,
            )
        hot_industries, hot_industry_source, hot_industry_source_text = self._resolve_hot_industries_cached(
            db=db,
            latest_trade_date=latest_trade_date,
            pooled_candidates=persisted_pool,
        )
        regime = self.market_data.get_market_regime_fast(
            latest_trade_date=latest_trade_date,
            hot_industries=hot_industries,
            hot_industry_source=hot_industry_source,
            hot_industry_source_text=hot_industry_source_text,
            recent_hot_sequences=self._load_recent_hot_industry_sequences(
                db=db,
                latest_trade_date=latest_trade_date,
            ),
        )
        return PriorityMarketContext(
            market_state=regime.state,
            market_bonus=regime.ranking_bonus,
            market_state_strength=regime.state_strength,
            regime_confidence=regime.regime_confidence,
            state_persistence_days=regime.state_persistence_days,
            transition_risk=regime.transition_risk,
            market_state_label=regime.label,
            market_state_description=regime.description,
            breadth_ready=regime.breadth_ready,
            emotion_ready=regime.emotion_ready,
            stock_up_ratio=regime.stock_up_ratio,
            stock_median_change=regime.stock_median_change,
            style_divergence=regime.style_divergence,
            hot_turnover=regime.hot_turnover,
            hot_overlap_ratio=regime.hot_overlap_ratio,
            limit_down_count=regime.limit_down_count,
            limit_up_count=regime.limit_up_count,
            board_height=regime.board_height,
            previous_board_height=regime.previous_board_height,
            promotion_ratio=regime.promotion_ratio,
            broken_board_ratio=regime.broken_board_ratio,
            promotion_break_gap=regime.promotion_break_gap,
            promotion_break_pressure=regime.promotion_break_pressure,
            high_flyer_retreat_ratio=regime.high_flyer_retreat_ratio,
            high_flyer_gap_speed=regime.high_flyer_gap_speed,
            distribution_pressure=regime.distribution_pressure,
            hot_industries=regime.hot_industries,
            hot_industry_source=regime.hot_industry_source,
            hot_industry_source_text=regime.hot_industry_source_text,
            mainline_lifecycle_state=regime.mainline_lifecycle_state,
            mainline_lifecycle_text=regime.mainline_lifecycle_text,
            industry_ranks=self._rank_hot_industries(regime.hot_industries),
        )

    def _primary_candidates_for_portfolio(
        self,
        rows: list[PriorityCandidate],
        market_context: PriorityMarketContext,
    ) -> list[LowBuyCandidateOut]:
        candidates: list[LowBuyCandidateOut] = []
        for row in rows:
            if not row.hits:
                continue
            aggregate_weight = self._aggregate_strategy_weight(row.hits)
            family_count = self._effective_family_count(row.hits)
            primary_hit = max(
                row.hits,
                key=lambda hit: self._final_rank_score(
                    candidate=hit.candidate,
                    aggregate_weight=aggregate_weight,
                    family_count=family_count,
                    strategy_weight=hit.strategy_weight_score + hit.context_bonus,
                    market_context=market_context,
                ),
            )
            candidates.append(primary_hit.candidate)
        return candidates
