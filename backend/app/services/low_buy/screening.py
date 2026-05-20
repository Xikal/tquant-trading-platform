from __future__ import annotations

from app.services.low_buy.shared import (
    DataSourceError,
    DEFAULT_PRODUCTION_LOW_BUY_STRATEGY,
    LowBuyHistoryResponse,
    LowBuyScreenerResponse,
    Session,
    SessionLocal,
    datetime,
)
from app.services.low_buy.screening_read import screen_read_path
from app.services.low_buy.screening_quotes import LowBuyQuoteRefreshMixin
from app.services.low_buy.factor_external import resolve_sector_flow_ranks
from app.services.low_buy.leader_strength_enrichment import enrich_low_buy_candidates_with_leader_strength
from app.services.low_buy.data_quality import build_market_data_quality, data_quality_payload
from app.services.low_buy.screening_helpers import (
    build_factor_sector_counts,
    build_screen_response,
    evaluate_scan_targets,
    prefilter_scan_targets,
    split_signal_candidates,
)
from app.repositories.low_buy import SystemSettingRepository
from app.services.low_buy.recommendation_duration import attach_response_recommendation_durations
from app.services.low_buy.strategy_policy import requires_mainline_industry
from app.services.market.state_categories import standard_market_state_payload


class LowBuyScreeningMixin(LowBuyQuoteRefreshMixin):
    def _rebuild_materialized_snapshot(
        self,
        db: Session,
        strategy: str,
        latest_trade_date: str,
        limit: int,
        include_history: bool,
    ) -> LowBuyScreenerResponse | None:
        """Rebuild materialized rows from persisted full-cache JSON.

        This method intentionally does not commit.  Callers own the
        transaction boundary so external sessions are never committed here.
        """

        setting_key = self._full_cache_setting_key(strategy, latest_trade_date, limit, include_history)
        row = SystemSettingRepository(db).fetch(setting_key)
        if row is None or not row.value or not self._response_payload_is_current(row.value):
            return None
        try:
            payload = LowBuyScreenerResponse.model_validate_json(row.value)
        except Exception:
            return None
        if payload.latest_trade_date != latest_trade_date or payload.strategy_key != strategy:
            return None
        self._persist_materialized_full_result(db=db, payload=payload)
        return attach_response_recommendation_durations(db=db, payload=payload)

    def refresh_full_scan_cache(
        self,
        strategy: str,
        limit: int = 16,
        scan_limit: int | None = None,
        include_history: bool = False,
        compute_performance: bool = True,
        build_close_review: bool = True,
    ) -> LowBuyScreenerResponse:
        with SessionLocal() as db:
            trade_dates = self._get_recent_trade_dates(14)
            latest_completed_trade_date = self._resolve_latest_completed_trade_date(trade_dates)
            payload = self._screen_sync(
                db=db,
                strategy=strategy,
                limit=limit,
                scan_limit=scan_limit or self._default_full_scan_limit,
                include_history=include_history,
                scan_mode="full",
                compute_performance=False,
            )
            if compute_performance:
                self._build_strategy_performance_snapshot(
                    db=db,
                    strategy=strategy,
                    latest_trade_date=payload.latest_trade_date,
                )
            payload = self._attach_strategy_performance(db=db, payload=payload, build_if_missing=False)
            self._save_persisted_full_result(
                db=db,
                payload=payload,
                limit=limit,
                include_history=include_history,
            )
            if not build_close_review:
                return payload
            self._build_close_review_snapshot(
                db=db,
                strategy=strategy,
                latest_trade_date=latest_completed_trade_date,
            )
            return self._attach_close_review_snapshot(
                db=db,
                payload=payload,
                review_trade_date=latest_completed_trade_date,
            )

    def screen(
        self,
        db: Session,
        strategy: str = DEFAULT_PRODUCTION_LOW_BUY_STRATEGY,
        limit: int = 16,
        scan_limit: int = 72,
        include_history: bool = False,
        scan_mode: str = "quick",
    ) -> LowBuyScreenerResponse:
        return screen_read_path(
            self,
            db=db,
            strategy=strategy,
            limit=limit,
            scan_limit=scan_limit,
            include_history=include_history,
            scan_mode=scan_mode,
        )

    def _screen_sync(
        self,
        db: Session,
        strategy: str = DEFAULT_PRODUCTION_LOW_BUY_STRATEGY,
        limit: int = 16,
        scan_limit: int = 72,
        include_history: bool = False,
        scan_mode: str = "quick",
        compute_performance: bool = True,
        history_wait_timeout_seconds: float | None = None,
    ) -> LowBuyScreenerResponse:
        playbook = self._get_playbook(strategy)
        trade_dates = self._get_recent_trade_dates(14)
        if len(trade_dates) < 3:
            raise DataSourceError("交易日历数据不足，暂时无法运行低吸选股。")

        latest_completed_trade_date = self._resolve_latest_completed_trade_date(trade_dates)
        latest_trade_date = self._resolve_active_structure_trade_date(
            trade_dates=trade_dates,
            latest_completed_trade_date=latest_completed_trade_date,
        )
        cache_key = self._make_screen_cache_key(
            strategy=strategy,
            latest_trade_date=latest_trade_date,
            limit=limit,
            scan_limit=scan_limit,
            include_history=include_history,
            scan_mode=scan_mode,
        )
        cached = self._get_screen_cache(cache_key)
        if cached is not None:
            cached = self._normalize_response_candidate_policy_state(cached)
            return attach_response_recommendation_durations(db=db, payload=cached).model_copy(deep=True)

        completed_trade_dates = [item for item in trade_dates if item <= latest_completed_trade_date]
        structure_trade_dates = list(completed_trade_dates)
        if latest_trade_date > latest_completed_trade_date:
            structure_trade_dates.append(latest_trade_date)
        board_window_days = self._strategy_board_window_days(strategy)
        retracement_days_max = self._strategy_retracement_days_max(strategy)
        board_dates = completed_trade_dates[-board_window_days:]
        ranked_pool = self._load_ranked_pool(
            db=db,
            latest_trade_date=latest_completed_trade_date,
            board_dates=board_dates,
        )
        pooled_candidates = {item.symbol: item for item in ranked_pool}
        hot_industries, hot_industry_source, hot_industry_source_text = self._resolve_hot_industries(
            db=db,
            latest_trade_date=latest_completed_trade_date,
            pooled_candidates=pooled_candidates,
        )
        if requires_mainline_industry(strategy) and hot_industry_source != "mainline_strength":
            hot_industries = []
            hot_industry_source_text = f"{hot_industry_source_text}；主线数据不足，本策略暂不进入生产执行。".strip("；")
        market_regime = self.market_data.get_market_regime(
            latest_trade_date=latest_completed_trade_date,
            hot_industries=hot_industries,
            hot_industry_source=hot_industry_source,
            hot_industry_source_text=hot_industry_source_text,
            recent_hot_sequences=self._load_recent_hot_industry_sequences(
                db=db,
                latest_trade_date=latest_completed_trade_date,
            ),
        )
        limit_down_count = market_regime.limit_down_count
        retracement_buckets = self._build_retracement_buckets(
            ranked_pool=ranked_pool,
            completed_trade_dates=structure_trade_dates,
            latest_trade_date=latest_trade_date,
            max_days=retracement_days_max,
        )
        scan_pool = self._build_balanced_scan_pool(retracement_buckets=retracement_buckets, scan_limit=scan_limit)
        confirmed_scan_pool = self._build_confirmed_scan_pool(retracement_buckets, per_day_limit=4, total_limit=12)

        scan_targets = (
            ranked_pool[: max(scan_limit, len(ranked_pool))]
            if scan_mode == "full"
            else self._merge_candidates(scan_pool, confirmed_scan_pool)
        )
        strategy_scan_pool = self._load_strategy_scan_pool(
            db=db,
            strategy=strategy,
            latest_trade_date=latest_completed_trade_date,
            scan_limit=scan_limit,
            hot_industries=hot_industries,
            ranked_pool=ranked_pool,
        )
        if strategy_scan_pool is not None:
            ranked_pool = strategy_scan_pool
            retracement_buckets = self._build_retracement_buckets(
                ranked_pool=ranked_pool,
                completed_trade_dates=structure_trade_dates,
                latest_trade_date=latest_trade_date,
                max_days=retracement_days_max,
            )
            scan_targets = strategy_scan_pool[: max(scan_limit, len(strategy_scan_pool))] if scan_mode == "full" else strategy_scan_pool[:scan_limit]
        scan_targets = self._prepare_strategy_scan_targets(
            strategy=strategy,
            scan_targets=scan_targets,
            hot_industries=hot_industries,
        )
        effective_scan_targets = prefilter_scan_targets(scan_targets)
        batch_quotes = self.market_data.get_quotes_batch([item.symbol for item in effective_scan_targets])
        histories = self._load_histories(
            effective_scan_targets,
            latest_completed_trade_date,
            active_trade_date=latest_trade_date,
            quote_map=batch_quotes,
            wait_timeout_seconds=history_wait_timeout_seconds,
        )
        factor_sector_counts = build_factor_sector_counts(effective_scan_targets)
        sector_flow_ranks = resolve_sector_flow_ranks()

        evaluated = evaluate_scan_targets(
            scan_targets=effective_scan_targets,
            histories=histories,
            strategy=strategy,
            latest_trade_date=latest_trade_date,
            hot_industries=hot_industries,
            market_regime=market_regime,
            factor_sector_counts=factor_sector_counts,
            sector_flow_ranks=sector_flow_ranks,
            evaluate_candidate=self._evaluate_candidate,
        )
        evaluated = self._dedupe_candidates(evaluated)
        evaluated = enrich_low_buy_candidates_with_leader_strength(
            db=db,
            candidates=evaluated,
            market_data=self.market_data,
        )
        evaluated = self._apply_live_quotes(evaluated, quote_map=batch_quotes)
        evaluated.sort(key=lambda item: (self._signal_rank(item.buy_signal_state), item.score), reverse=True)

        confirmed_candidates, candidates = split_signal_candidates(
            evaluated,
            confirmed_states=self._confirmed_signal_states,
            limit=limit,
        )
        history_sections = (
            self._build_history_sections(completed_trade_dates[-4:-1], strategy)
            if include_history and strategy == "classic_retrace"
            else []
        )
        as_of_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        market_state_fields = standard_market_state_payload(market_regime.state)
        market_quality = build_market_data_quality(
            breadth_ready=market_regime.breadth_ready,
            emotion_ready=market_regime.emotion_ready,
            hot_industry_source=hot_industry_source,
        )
        quality_fields = data_quality_payload(market_quality)
        response = build_screen_response(
            strategy=strategy,
            playbook=playbook,
            scan_mode=scan_mode,
            as_of_date=as_of_date,
            latest_trade_date=latest_trade_date,
            latest_completed_trade_date=latest_completed_trade_date,
            ranked_pool=ranked_pool,
            scan_targets=scan_targets,
            confirmed_candidates=confirmed_candidates,
            candidates=candidates,
            history_sections=history_sections,
            retracement_buckets=retracement_buckets,
            board_window_days=board_window_days,
            scan_limit=scan_limit,
            retracement_days_max=retracement_days_max,
            pool_profile_text=self._strategy_pool_profile_text(strategy),
            market_regime=market_regime,
            market_state_fields=market_state_fields,
            quality_fields=quality_fields,
            hot_industries=hot_industries,
            hot_industry_source=hot_industry_source,
            hot_industry_source_text=hot_industry_source_text,
            limit_down_count=limit_down_count,
            strategy_notes=self._build_strategy_notes(
                [*playbook["notes"], f"当前市场状态：{market_regime.label}。{market_regime.description}"],
                hot_industries,
                limit_down_count,
                hot_industry_source_text=hot_industry_source_text,
            ),
        )
        response = attach_response_recommendation_durations(db=db, payload=response)
        if compute_performance:
            response = self._attach_strategy_performance(
                db=db,
                payload=response,
                build_if_missing=False,
            )
        self._set_screen_cache(
            cache_key,
            response,
            ttl=self._screen_cache_ttl_full if scan_mode == "full" else self._screen_cache_ttl,
        )
        if scan_mode == "full":
            self._save_persisted_full_result(db=db, payload=response, limit=limit, include_history=include_history)
        return response

    def history(self, db: Session, strategy: str = DEFAULT_PRODUCTION_LOW_BUY_STRATEGY) -> LowBuyHistoryResponse:
        self._get_playbook(strategy)
        trade_dates = self._get_recent_trade_dates(14)
        latest_trade_date = self._resolve_latest_completed_trade_date(trade_dates)
        cache_key = f"history-only:{strategy}:{latest_trade_date}"
        cached = self._get_history_cache(cache_key)
        if cached is not None:
            return cached
        completed_trade_dates = [item for item in trade_dates if item <= latest_trade_date]
        response = LowBuyHistoryResponse(
            as_of_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            latest_trade_date=latest_trade_date,
            history_sections=self._build_history_sections(
                completed_trade_dates[-4:-1],
                strategy,
                db=db,
            ),
        )
        performance = self._resolve_strategy_performance(
            db=db,
            strategy=strategy,
            latest_trade_date=latest_trade_date,
            build_if_missing=False,
        )
        response = response.model_copy(
            update={
                "history_sections": self._apply_strategy_performance_to_history_sections(
                    response.history_sections,
                    performance,
                )
            }
        )
        self._set_history_cache(cache_key, response)
        return response
