from __future__ import annotations

from app.services.low_buy.shared import (
    DataSourceError,
    DEFAULT_PRODUCTION_LOW_BUY_STRATEGY,
    LOW_BUY_THRESHOLDS,
    LOW_BUY_RESULT_VERSION,
    LowBuyCandidateOut,
    LowBuyHistoryResponse,
    LowBuyScreenerResponse,
    PERFORMANCE_LOOKBACK_DAYS,
    Session,
    SessionLocal,
    ak,
    datetime,
    json,
)
from app.services.low_buy.screening_quotes import LowBuyQuoteRefreshMixin
from app.services.low_buy.factor_types import FactorContext
from app.services.low_buy.factor_external import resolve_sector_flow_ranks
from app.services.low_buy.data_quality import build_market_data_quality, data_quality_payload
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
        db.commit()
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
        if scan_mode not in {"quick", "full"}:
            raise DataSourceError(f"未知扫描模式: {scan_mode}")
        trade_dates = self._get_recent_trade_dates(14)
        if len(trade_dates) < 3:
            raise DataSourceError("交易日历数据不足，暂时无法运行低吸选股。")
        latest_completed_trade_date = self._resolve_latest_completed_trade_date(trade_dates)
        latest_trade_date = self._resolve_active_structure_trade_date(
            trade_dates=trade_dates,
            latest_completed_trade_date=latest_completed_trade_date,
        )
        cached_full = self._load_cached_full_result(
            db=db,
            strategy=strategy,
            latest_trade_date=latest_trade_date,
            limit=limit,
            include_history=include_history,
        )
        if scan_mode == "full" and cached_full is not None:
            cached_full = self._attach_strategy_performance(
                db=db,
                payload=cached_full,
                build_if_missing=False,
            )
            cached_full = self._attach_close_review_snapshot(
                db=db,
                payload=cached_full,
                review_trade_date=latest_completed_trade_date,
                build_if_missing=False,
            )
            return cached_full.model_copy(
                update={
                    "requested_mode": "full",
                    "response_mode": "full",
                    "full_scan_ready": True,
                    "full_scan_in_progress": False,
                    "full_scan_updated_at": cached_full.as_of_date,
                }
            )

        full_in_progress = self._is_full_scan_running(
            strategy=strategy,
            latest_trade_date=latest_trade_date,
            limit=limit,
            include_history=include_history,
        )

        if scan_mode == "full":
            last_completed = self._load_latest_materialized_full_result(
                db=db,
                strategy=strategy,
                limit=limit,
                include_history=include_history,
                allow_repair=False,
            )
            if last_completed is not None:
                last_completed = self._attach_strategy_performance(
                    db=db,
                    payload=last_completed,
                    build_if_missing=False,
                )
                last_completed = self._attach_close_review_snapshot(
                    db=db,
                    payload=last_completed,
                    review_trade_date=latest_completed_trade_date,
                    build_if_missing=False,
                )
                return last_completed.model_copy(
                    update={
                        "requested_mode": "full",
                        "response_mode": "full",
                        "full_scan_ready": True,
                        "full_scan_in_progress": full_in_progress,
                        "full_scan_updated_at": last_completed.as_of_date,
                    }
                )
            placeholder_performance = self._load_strategy_performance_snapshot(
                db=db,
                strategy=strategy,
                latest_trade_date=latest_trade_date,
            ) or self._empty_strategy_performance(
                target_profit_pct=self._load_stock_profit_target_pct(db),
                lookback_days=PERFORMANCE_LOOKBACK_DAYS,
                note="后台全量深筛仍在补齐，当前先显示等待状态。",
            )
            pending = self._build_pending_full_response(
                strategy=strategy,
                latest_trade_date=latest_trade_date,
                requested_scan_limit=self._resolve_full_scan_limit(scan_limit),
                performance=placeholder_performance,
                full_scan_in_progress=full_in_progress,
            )
            return self._attach_close_review_snapshot(
                db=db,
                payload=pending,
                review_trade_date=latest_completed_trade_date,
                build_if_missing=False,
            )

        latest_snapshot = self._load_latest_materialized_full_result(
            db=db,
            strategy=strategy,
            limit=limit,
            include_history=include_history,
            allow_repair=False,
        )
        if latest_snapshot is not None:
            latest_snapshot = self._attach_strategy_performance(
                db=db,
                payload=latest_snapshot,
                build_if_missing=False,
            )
            latest_snapshot = self._attach_close_review_snapshot(
                db=db,
                payload=latest_snapshot,
                review_trade_date=latest_completed_trade_date,
                build_if_missing=False,
            )
            return latest_snapshot.model_copy(
                update={
                    "requested_mode": scan_mode,
                    "response_mode": "full",
                    "full_scan_ready": True,
                    "full_scan_in_progress": full_in_progress,
                    "full_scan_updated_at": latest_snapshot.full_scan_updated_at or latest_snapshot.as_of_date,
                }
            )

        placeholder_performance = self._load_strategy_performance_snapshot(
            db=db,
            strategy=strategy,
            latest_trade_date=latest_trade_date,
        ) or self._empty_strategy_performance(
            target_profit_pct=self._load_stock_profit_target_pct(db),
            lookback_days=PERFORMANCE_LOOKBACK_DAYS,
            note="后台全量深筛仍在补齐，当前先显示等待状态。",
        )
        pending = self._build_pending_full_response(
            strategy=strategy,
            latest_trade_date=latest_trade_date,
            requested_scan_limit=self._resolve_full_scan_limit(scan_limit),
            performance=placeholder_performance,
            full_scan_in_progress=full_in_progress,
        )
        pending = self._attach_close_review_snapshot(
            db=db,
            payload=pending,
            review_trade_date=latest_completed_trade_date,
            build_if_missing=False,
        )
        return pending.model_copy(update={"requested_mode": scan_mode, "response_mode": "pending"})

    def _build_pending_full_response(
        self,
        strategy: str,
        latest_trade_date: str,
        requested_scan_limit: int,
        performance,
        full_scan_in_progress: bool,
    ) -> LowBuyScreenerResponse:
        playbook = self._get_playbook(strategy)
        as_of_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return LowBuyScreenerResponse(
            strategy_key=strategy,
            strategy_title=playbook["title"],
            strategy_subtitle=playbook["subtitle"],
            strategy_logic=playbook["logic"],
            requested_mode="full",
            response_mode="full",
            as_of_date=as_of_date,
            latest_trade_date=latest_trade_date,
            pool_size=0,
            scanned_count=0,
            matched_count=0,
            requested_scan_limit=requested_scan_limit,
            active_scan_limit=0,
            full_scan_ready=False,
            full_scan_in_progress=full_scan_in_progress,
            full_scan_updated_at=None,
            market_state_category="low_volume_wait",
            market_state_category_text="缩量无主线",
            data_quality="limited",
            data_quality_text="后台全量深筛仍在补齐",
            data_quality_tags=["全量快照待生成"],
            retracement_distribution={},
            filters={
                "scan_mode": "全量物化",
                "market_state_category": "low_volume_wait",
                "market_state_category_text": "缩量无主线",
                "data_quality": "limited",
                "data_quality_text": "后台全量深筛仍在补齐",
                "data_quality_tags_json": json.dumps(["全量快照待生成"], ensure_ascii=False),
                "_result_version": LOW_BUY_RESULT_VERSION,
            },
            strategy_notes=list(playbook["notes"]),
            performance=performance,
            confirmed_candidates=[],
            history_sections=[],
            candidates=[],
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
        if ak is None:
            raise DataSourceError("当前环境未安装 akshare，无法运行低吸选股。")
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
        effective_scan_targets = self._prefilter_scan_targets(scan_targets)
        batch_quotes = self.market_data.get_quotes_batch([item.symbol for item in effective_scan_targets])
        histories = self._load_histories(
            effective_scan_targets,
            latest_completed_trade_date,
            active_trade_date=latest_trade_date,
            quote_map=batch_quotes,
            wait_timeout_seconds=history_wait_timeout_seconds,
        )
        factor_sector_counts = self._build_factor_sector_counts(effective_scan_targets)
        sector_flow_ranks = resolve_sector_flow_ranks()

        evaluated: list[LowBuyCandidateOut] = []
        for item in effective_scan_targets:
            candidate = self._evaluate_candidate(
                item=item,
                latest_trade_date=latest_trade_date,
                history=histories.get(item.symbol),
                strategy=strategy,
                hot_industries=hot_industries,
                market_regime=market_regime,
                factor_context=self._build_factor_context(
                    item=item,
                    sector_counts=factor_sector_counts,
                    latest_trade_date=latest_trade_date,
                    sector_flow_ranks=sector_flow_ranks,
                ),
            )
            if candidate is not None:
                evaluated.append(candidate)

        evaluated = self._dedupe_candidates(evaluated)
        evaluated = self._apply_live_quotes(evaluated, quote_map=batch_quotes)
        evaluated.sort(key=lambda item: (self._signal_rank(item.buy_signal_state), item.score), reverse=True)

        confirmed_candidates = [
            item for item in evaluated if item.buy_signal_state in self._confirmed_signal_states
        ][:12]
        candidates = [
            item for item in evaluated if item.buy_signal_state not in self._confirmed_signal_states
        ][:limit]
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
        response = LowBuyScreenerResponse(
            strategy_key=strategy,
            strategy_title=playbook["title"],
            strategy_subtitle=playbook["subtitle"],
            strategy_logic=playbook["logic"],
            requested_mode=scan_mode,
            response_mode=scan_mode,
            as_of_date=as_of_date,
            latest_trade_date=latest_trade_date,
            pool_size=len(ranked_pool),
            scanned_count=len(scan_targets),
            matched_count=len(confirmed_candidates) + len(candidates),
            requested_scan_limit=scan_limit,
            active_scan_limit=len(scan_targets),
            full_scan_ready=scan_mode == "full",
            full_scan_in_progress=False,
            full_scan_updated_at=as_of_date if scan_mode == "full" else None,
            market_state=market_regime.state,
            market_state_text=market_regime.label,
            market_state_category=market_state_fields["market_state_category"],
            market_state_category_text=market_state_fields["market_state_category_text"],
            **quality_fields,
            market_bonus=market_regime.ranking_bonus,
            market_state_strength=market_regime.state_strength,
            regime_confidence=market_regime.regime_confidence,
            state_persistence_days=market_regime.state_persistence_days,
            transition_risk=market_regime.transition_risk,
            breadth_ready=market_regime.breadth_ready,
            emotion_ready=market_regime.emotion_ready,
            stock_up_ratio=market_regime.stock_up_ratio,
            stock_median_change=market_regime.stock_median_change,
            style_divergence=market_regime.style_divergence,
            hot_turnover=market_regime.hot_turnover,
            hot_overlap_ratio=market_regime.hot_overlap_ratio,
            limit_down_count=market_regime.limit_down_count,
            limit_up_count=market_regime.limit_up_count,
            board_height=market_regime.board_height,
            previous_board_height=market_regime.previous_board_height,
            promotion_ratio=market_regime.promotion_ratio,
            broken_board_ratio=market_regime.broken_board_ratio,
            promotion_break_gap=market_regime.promotion_break_gap,
            promotion_break_pressure=market_regime.promotion_break_pressure,
            high_flyer_retreat_ratio=market_regime.high_flyer_retreat_ratio,
            high_flyer_gap_speed=market_regime.high_flyer_gap_speed,
            distribution_pressure=market_regime.distribution_pressure,
            hot_industries=hot_industries,
            hot_industry_source=hot_industry_source,
            hot_industry_source_text=hot_industry_source_text,
            mainline_lifecycle_state=market_regime.mainline_lifecycle_state,
            mainline_lifecycle_text=market_regime.mainline_lifecycle_text,
            retracement_distribution={f"{days}天": len(items) for days, items in sorted(retracement_buckets.items()) if items},
            filters={
                "board_window_days": board_window_days,
                "scan_limit": scan_limit,
                "scan_mode": "全量深筛，优先读取物化结果与候选池快照",
                "retracement_days_max": retracement_days_max,
                "pool_profile": self._strategy_pool_profile_text(strategy),
                "support_zone": "分歧高点突破区" if strategy == "divergence_consensus" else "5日/10日均线附近",
                "volume_rule": "底部涨停放量 + 横盘缩量 + 倍量突破" if strategy == "divergence_consensus" else "启动放量 + 回调缩量",
                "market_regime": market_regime.label,
                "market_state": market_regime.state,
                "market_state_category": market_state_fields["market_state_category"],
                "market_state_category_text": market_state_fields["market_state_category_text"],
                "market_regime_text": market_regime.description,
                "data_quality": quality_fields["data_quality"],
                "data_quality_text": quality_fields["data_quality_text"],
                "data_quality_tags_json": json.dumps(quality_fields["data_quality_tags"], ensure_ascii=False),
                "market_state_strength": market_regime.state_strength,
                "regime_confidence": market_regime.regime_confidence,
                "state_persistence_days": market_regime.state_persistence_days,
                "transition_risk": market_regime.transition_risk,
                "breadth_ready": market_regime.breadth_ready,
                "emotion_ready": market_regime.emotion_ready,
                "market_bonus": market_regime.ranking_bonus,
                "hot_industries": " / ".join(hot_industries) if hot_industries else "热点过滤不可用",
                "hot_industries_json": json.dumps(hot_industries, ensure_ascii=False),
                "hot_industry_source": hot_industry_source,
                "hot_industry_source_text": hot_industry_source_text,
                "limit_down_count": limit_down_count if limit_down_count is not None else "未获取",
                "limit_up_count": market_regime.limit_up_count,
                "board_height": market_regime.board_height,
                "promotion_ratio": market_regime.promotion_ratio,
                "broken_board_ratio": market_regime.broken_board_ratio,
                "high_flyer_retreat_ratio": market_regime.high_flyer_retreat_ratio,
                "stock_up_ratio": market_regime.stock_up_ratio,
                "stock_median_change": market_regime.stock_median_change,
                "style_divergence": market_regime.style_divergence,
                "hot_turnover": market_regime.hot_turnover,
                "hot_overlap_ratio": market_regime.hot_overlap_ratio,
                "previous_board_height": market_regime.previous_board_height,
                "promotion_break_gap": market_regime.promotion_break_gap,
                "promotion_break_pressure": market_regime.promotion_break_pressure,
                "high_flyer_gap_speed": market_regime.high_flyer_gap_speed,
                "distribution_pressure": market_regime.distribution_pressure,
                "mainline_lifecycle_state": market_regime.mainline_lifecycle_state,
                "mainline_lifecycle_text": market_regime.mainline_lifecycle_text,
                "structure_mode": "盘中临时结构样本" if latest_trade_date > latest_completed_trade_date else "完整日线样本",
                "_result_version": LOW_BUY_RESULT_VERSION,
            },
            strategy_notes=self._build_strategy_notes(
                [*playbook["notes"], f"当前市场状态：{market_regime.label}。{market_regime.description}"],
                hot_industries,
                limit_down_count,
                hot_industry_source_text=hot_industry_source_text,
            ),
            performance=None,
            confirmed_candidates=confirmed_candidates,
            history_sections=history_sections,
            candidates=candidates,
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

    @staticmethod
    def _build_factor_sector_counts(scan_targets) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in scan_targets:
            sector = item.industry or "未分类"
            counts[sector] = counts.get(sector, 0) + 1
        return counts

    @staticmethod
    def _prefilter_scan_targets(scan_targets):
        """Drop obvious non-tradable tails before quote/history fan-out.

        The full strategy rules still run on the remaining candidates.  If the
        cheap filter would leave too few candidates, fall back to the original
        pool to avoid changing strategy semantics for sparse pools.
        """
        if len(scan_targets) <= 80:
            return scan_targets
        min_amount = float(LOW_BUY_THRESHOLDS.MIN_DAILY_AMOUNT_AUXILIARY)
        filtered = [
            item
            for item in scan_targets
            if getattr(item, "symbol", "") and float(getattr(item, "amount", 0.0) or 0.0) >= min_amount
        ]
        minimum_keep = max(30, int(len(scan_targets) * 0.25))
        return filtered if len(filtered) >= minimum_keep else scan_targets

    @staticmethod
    def _build_factor_context(
        item,
        sector_counts: dict[str, int],
        latest_trade_date: str,
        sector_flow_ranks: dict[str, float] | None = None,
    ) -> FactorContext:
        return FactorContext(
            sector_pass_counts=sector_counts,
            sector_flow_ranks=sector_flow_ranks or {},
            current_sector=item.industry or "未分类",
            current_symbol=getattr(item, "symbol", ""),
            retracement_days=getattr(item, "retracement_days", _estimate_retracement_days(item, latest_trade_date)),
            confirmed_trade_date=latest_trade_date,
            current_date=latest_trade_date,
            total_strategies=1,
        )

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


def _estimate_retracement_days(item, latest_trade_date: str) -> int:
    try:
        board_date = datetime.strptime(getattr(item, "board_date", "")[:10], "%Y-%m-%d")
        latest_date = datetime.strptime(latest_trade_date[:10], "%Y-%m-%d")
        return max((latest_date - board_date).days, 0)
    except (TypeError, ValueError):
        return 0
