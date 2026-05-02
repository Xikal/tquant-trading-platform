from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, wait
import logging
import time
from datetime import datetime, timedelta

from app.repositories.low_buy import DailyBarRow, DailyHistoryRepository, LowBuyResultRepository
from app.services.low_buy.shared import (
    BoardCandidate,
    DEFAULT_PRODUCTION_LOW_BUY_STRATEGY,
    LOW_BUY_RESULT_VERSION,
    LowBuyCandidateOut,
    LowBuyHistoryResponse,
    LowBuyHistorySectionOut,
    LowBuyScreenerResponse,
    Session,
    SessionLocal,
    ak,
    datetime as shared_datetime,
    json,
    pd,
)
from app.services.low_buy.factor_types import FactorContext
from app.services.low_buy.strategy_policy import requires_mainline_industry

logger = logging.getLogger(__name__)


class LowBuyHistoryMixin:
    def _build_confirmed_scan_pool(
        self,
        retracement_buckets: dict[int, list[BoardCandidate]],
        per_day_limit: int = 4,
        total_limit: int = 12,
    ) -> list[BoardCandidate]:
        focused_days = [2, 3, 4]
        selected: list[BoardCandidate] = []
        for day in focused_days:
            selected.extend(retracement_buckets.get(day, [])[:per_day_limit])
        return self._dedupe_board_candidates(selected)[:total_limit]

    def _screen_confirmed_for_trade_date(
        self,
        latest_trade_date: str,
        strategy: str = DEFAULT_PRODUCTION_LOW_BUY_STRATEGY,
        max_candidates: int = 12,
    ) -> list[LowBuyCandidateOut]:
        cache_key = f"history-confirmed:{strategy}:{latest_trade_date}:{max_candidates}"
        cached = self._get_screen_cache(cache_key)
        if cached is not None:
            return [item.model_copy(deep=True) for item in cached.confirmed_candidates]
        confirmed_candidates = self._load_materialized_confirmed_candidates(latest_trade_date=latest_trade_date, strategy=strategy, max_candidates=max_candidates)
        playbook = self._get_playbook(strategy)
        payload = LowBuyScreenerResponse(
            strategy_key=strategy,
            strategy_title=playbook["title"],
            strategy_subtitle=playbook["subtitle"],
            strategy_logic=playbook["logic"],
            as_of_date=shared_datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            latest_trade_date=latest_trade_date,
            pool_size=0,
            scanned_count=0,
            matched_count=len(confirmed_candidates),
            retracement_distribution={},
            filters={},
            strategy_notes=list(playbook["notes"]),
            performance=None,
            confirmed_candidates=confirmed_candidates,
            history_sections=[],
            candidates=[],
        )
        self._set_screen_cache(cache_key, payload)
        return [item.model_copy(deep=True) for item in payload.confirmed_candidates]

    def _build_history_sections(
        self,
        historical_dates: list[str],
        strategy: str,
        db: Session | None = None,
    ) -> list[LowBuyHistorySectionOut]:
        sections: list[LowBuyHistorySectionOut] = []
        if not historical_dates:
            return sections
        yesterday = historical_dates[-1]
        yesterday_candidates = self._load_materialized_confirmed_candidates(
            latest_trade_date=yesterday,
            strategy=strategy,
            max_candidates=8,
            db=db,
        )
        sections.append(LowBuyHistorySectionOut(title="昨日确定买入", description=f"回看 {yesterday} 收盘后触发确定买入的名单，用于对照隔日表现。", candidates=yesterday_candidates))

        recent_candidates: list[LowBuyCandidateOut] = []
        for trade_date in reversed(historical_dates):
            materialized = self._load_materialized_confirmed_candidates(
                latest_trade_date=trade_date,
                strategy=strategy,
                max_candidates=8,
                db=db,
            )
            if materialized:
                recent_candidates.extend(materialized)
        deduped_recent = self._dedupe_candidates(recent_candidates)
        deduped_recent.sort(key=lambda item: ((item.confirmed_trade_date or ""), item.score), reverse=True)
        sections.append(LowBuyHistorySectionOut(title="最近3日确定买入", description=f"聚合 {historical_dates[0]} 至 {historical_dates[-1]} 之间曾触发确定买入的标的。", candidates=deduped_recent[:12]))
        return sections

    def _load_materialized_confirmed_candidates(
        self,
        latest_trade_date: str,
        strategy: str,
        max_candidates: int,
        db: Session | None = None,
    ) -> list[LowBuyCandidateOut]:
        if db is None:
            with SessionLocal() as local_db:
                return self._load_materialized_confirmed_candidates(
                    latest_trade_date=latest_trade_date,
                    strategy=strategy,
                    max_candidates=max_candidates,
                    db=local_db,
                )
        if not self._materialized_scan_is_current(
            db=db,
            strategy=strategy,
            latest_trade_date=latest_trade_date,
        ):
            return []
        rows = LowBuyResultRepository(db).fetch_confirmed_results(
            latest_trade_date=latest_trade_date,
            strategy_key=strategy,
            limit=max_candidates,
        )
        candidates: list[LowBuyCandidateOut] = []
        for row in rows:
            if not self._candidate_payload_is_current(row.payload_json):
                continue
            try:
                candidates.append(LowBuyCandidateOut.model_validate_json(row.payload_json))
            except Exception:
                continue
        return candidates

    def _ensure_historical_materialization(self, db: Session, strategy: str, trade_dates: list[str]) -> None:
        return

    def _screen_historical_sync(self, db: Session, strategy: str, latest_trade_date: str, limit: int, scan_limit: int) -> LowBuyScreenerResponse:
        playbook = self._get_playbook(strategy)
        trade_dates = [item for item in self._get_recent_trade_dates(760) if item <= latest_trade_date]
        if len(trade_dates) < 3:
            raise RuntimeError("历史交易日不足，无法回放策略表现。")
        board_window_days = self._strategy_board_window_days(strategy)
        retracement_days_max = self._strategy_retracement_days_max(strategy)
        board_dates = trade_dates[-board_window_days:]
        ranked_pool = self._load_ranked_pool(db=db, latest_trade_date=latest_trade_date, board_dates=board_dates)
        pooled_candidates = {item.symbol: item for item in ranked_pool}
        hot_industries, hot_industry_source, hot_industry_source_text = self._resolve_hot_industries(
            db=db,
            latest_trade_date=latest_trade_date,
            pooled_candidates=pooled_candidates,
        )
        if requires_mainline_industry(strategy) and hot_industry_source != "mainline_strength":
            hot_industries = []
            hot_industry_source_text = f"{hot_industry_source_text}；主线数据不足，本策略暂不进入生产执行。".strip("；")
        market_regime = self.market_data.get_market_regime(
            latest_trade_date=latest_trade_date,
            hot_industries=hot_industries,
            hot_industry_source=hot_industry_source,
            hot_industry_source_text=hot_industry_source_text,
            recent_hot_sequences=self._load_recent_hot_industry_sequences(
                db=db,
                latest_trade_date=latest_trade_date,
            ),
        )
        limit_down_count = market_regime.limit_down_count
        retracement_buckets = self._build_retracement_buckets(
            ranked_pool=ranked_pool,
            completed_trade_dates=trade_dates,
            latest_trade_date=latest_trade_date,
            max_days=retracement_days_max,
        )
        scan_targets = ranked_pool[: max(scan_limit, len(ranked_pool))]
        strategy_scan_pool = self._load_strategy_scan_pool(
            db=db,
            strategy=strategy,
            latest_trade_date=latest_trade_date,
            scan_limit=scan_limit,
            hot_industries=hot_industries,
            ranked_pool=ranked_pool,
        )
        if strategy_scan_pool is not None:
            ranked_pool = strategy_scan_pool
            retracement_buckets = self._build_retracement_buckets(
                ranked_pool=ranked_pool,
                completed_trade_dates=trade_dates,
                latest_trade_date=latest_trade_date,
                max_days=retracement_days_max,
            )
            scan_targets = strategy_scan_pool[: max(scan_limit, len(strategy_scan_pool))]
        scan_targets = self._prepare_strategy_scan_targets(
            strategy=strategy,
            scan_targets=scan_targets,
            hot_industries=hot_industries,
        )
        histories = self._load_histories(scan_targets, latest_trade_date)
        sector_counts = self._build_factor_sector_counts(scan_targets)

        evaluated: list[LowBuyCandidateOut] = []
        for item in scan_targets:
            history = histories.get(item.symbol)
            candidate = self._evaluate_candidate(
                item=item,
                latest_trade_date=latest_trade_date,
                history=history,
                strategy=strategy,
                hot_industries=hot_industries,
                market_regime=market_regime,
                factor_context=FactorContext(
                    sector_pass_counts=sector_counts,
                    current_sector=item.industry or "未分类",
                    confirmed_trade_date=latest_trade_date,
                    current_date=latest_trade_date,
                    total_strategies=1,
                ),
            )
            if candidate is None or history is None or history.empty:
                continue
            latest_rows = history.index[history["date"] == latest_trade_date].tolist()
            if latest_rows:
                evaluated.append(self._refresh_historical_buy_signal(candidate, history.iloc[latest_rows[-1]]))

        evaluated = self._dedupe_candidates(evaluated)
        evaluated.sort(key=lambda item: (self._signal_rank(item.buy_signal_state), item.score), reverse=True)
        confirmed_candidates = [
            item for item in evaluated if item.buy_signal_state in self._confirmed_signal_states
        ][:12]
        candidates = [
            item for item in evaluated if item.buy_signal_state not in self._confirmed_signal_states
        ][:limit]
        as_of_date = shared_datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return LowBuyScreenerResponse(
            strategy_key=strategy,
            strategy_title=playbook["title"],
            strategy_subtitle=playbook["subtitle"],
            strategy_logic=playbook["logic"],
            requested_mode="full",
            response_mode="full",
            as_of_date=as_of_date,
            latest_trade_date=latest_trade_date,
            pool_size=len(ranked_pool),
            scanned_count=len(scan_targets),
            matched_count=len(confirmed_candidates) + len(candidates),
            requested_scan_limit=scan_limit,
            active_scan_limit=len(scan_targets),
            full_scan_ready=True,
            full_scan_in_progress=False,
            full_scan_updated_at=as_of_date,
            retracement_distribution={f"{days}天": len(items) for days, items in sorted(retracement_buckets.items()) if items},
            filters={
                "board_window_days": board_window_days,
                "scan_limit": scan_limit,
                "scan_mode": "历史回放",
                "retracement_days_max": retracement_days_max,
                "pool_profile": self._strategy_pool_profile_text(strategy),
                "support_zone": "分歧高点突破区" if strategy == "divergence_consensus" else "5日/10日均线附近",
                "volume_rule": "底部涨停放量 + 横盘缩量 + 倍量突破" if strategy == "divergence_consensus" else "启动放量 + 回调缩量",
                "market_regime": market_regime.label,
                "market_state": market_regime.state,
                "market_regime_text": market_regime.description,
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
                "structure_mode": "完整日线样本",
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
            history_sections=[],
            candidates=candidates,
        )
    @staticmethod
    def _build_factor_sector_counts(scan_targets) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in scan_targets:
            sector = item.industry or "未分类"
            counts[sector] = counts.get(sector, 0) + 1
        return counts

    def _load_daily_history(self, symbol: str, latest_trade_date: str, history_window_days: int = 180) -> pd.DataFrame | None:
        cache_key = f"{symbol}:{latest_trade_date}:{history_window_days}"
        cached = self._get_daily_history_cache(cache_key)
        if cached is not None:
            return cached.copy(deep=True) if cached is not None else None

        start_date = datetime.strptime(latest_trade_date, "%Y-%m-%d") - timedelta(days=history_window_days)
        start_date_iso = start_date.date().isoformat()
        with SessionLocal() as db:
            normalized = self._load_daily_history_from_db(db=db, symbol=symbol, start_date_iso=start_date_iso, latest_trade_date=latest_trade_date)
            latest_local_date = str(normalized["date"].iloc[-1]) if normalized is not None and not normalized.empty else None
            needs_sync = normalized is None or normalized.empty or len(normalized) < 60 or latest_local_date != latest_trade_date
            if needs_sync:
                sync_start_iso = start_date_iso
                if latest_local_date and normalized is not None and not normalized.empty and len(normalized) >= 60:
                    overlap_start = datetime.strptime(latest_local_date, "%Y-%m-%d") - timedelta(days=7)
                    sync_start_iso = max(start_date_iso, overlap_start.date().isoformat())
                remote_history = self._fetch_remote_daily_history(symbol=symbol, start_date_iso=sync_start_iso, latest_trade_date=latest_trade_date)
                if remote_history is not None and not remote_history.empty:
                    self._persist_daily_history_rows(db=db, symbol=symbol, history=remote_history)
                    normalized = self._load_daily_history_from_db(db=db, symbol=symbol, start_date_iso=start_date_iso, latest_trade_date=latest_trade_date)

        if normalized is None or normalized.empty:
            return None
        self._set_daily_history_cache(cache_key, normalized)
        return normalized.copy(deep=True)

    def _load_daily_history_from_db(self, db: Session, symbol: str, start_date_iso: str, latest_trade_date: str) -> pd.DataFrame | None:
        rows = DailyHistoryRepository(db).fetch_rows(
            symbol=symbol,
            start_date_iso=start_date_iso,
            latest_trade_date=latest_trade_date,
        )
        if not rows:
            return None
        normalized = pd.DataFrame(
            [
                {
                    "date": row.trade_date,
                    "open": row.open_price,
                    "close": row.close_price,
                    "high": row.high_price,
                    "low": row.low_price,
                    "volume": row.volume,
                    "amount": row.amount,
                    "pct_chg": row.pct_chg,
                }
                for row in rows
            ]
        )
        return self._finalize_daily_history_frame(normalized, start_date_iso)

    def _fetch_remote_daily_history(self, symbol: str, start_date_iso: str, latest_trade_date: str) -> pd.DataFrame | None:
        start_date_str = start_date_iso.replace("-", "")
        end_date_str = latest_trade_date.replace("-", "")
        normalized: pd.DataFrame | None = None
        try:
            frame = self.market_data._call_akshare(
                ak.stock_zh_a_daily,
                symbol=self.market_data._to_sina_symbol(symbol),
                start_date=start_date_str,
                end_date=end_date_str,
                adjust="qfq",
                purpose="daily_history",
            )
            if not frame.empty:
                normalized = frame.rename(columns={"date": "date", "open": "open", "close": "close", "high": "high", "low": "low", "volume": "volume", "amount": "amount"}).copy()
                normalized["pct_chg"] = normalized["close"].pct_change().fillna(0.0) * 100
        except Exception:
            normalized = None
        if normalized is None:
            try:
                frame = self.market_data._call_akshare(
                    ak.stock_zh_a_hist_tx,
                    symbol=self.market_data._to_sina_symbol(symbol),
                    start_date=start_date_str,
                    end_date=end_date_str,
                    purpose="daily_history",
                )
                if frame.empty:
                    return None
                normalized = frame.rename(columns={"date": "date", "open": "open", "close": "close", "high": "high", "low": "low", "amount": "volume"}).copy()
                normalized["amount"] = 0.0
                normalized["pct_chg"] = normalized["close"].pct_change().fillna(0.0) * 100
            except Exception:
                return None
        return self._finalize_daily_history_frame(normalized, start_date_iso)

    def _build_intraday_history(self, history: pd.DataFrame | None, active_trade_date: str, quote) -> pd.DataFrame | None:
        if history is None or history.empty or quote is None or str(history["date"].iloc[-1]) >= active_trade_date:
            return history
        last_price = float(getattr(quote, "last_price", 0.0) or 0.0)
        open_price = float(getattr(quote, "open_price", 0.0) or 0.0)
        high_price = float(getattr(quote, "high_price", 0.0) or 0.0)
        low_price = float(getattr(quote, "low_price", 0.0) or 0.0)
        prev_close = float(getattr(quote, "prev_close", 0.0) or float(history["close"].iloc[-1]) or 0.0)
        volume = float(getattr(quote, "volume", 0.0) or 0.0)
        amount = float(getattr(quote, "amount", 0.0) or 0.0)
        if last_price <= 0:
            return history
        synthetic_bar = {
            "date": active_trade_date,
            "open": open_price if open_price > 0 else prev_close,
            "close": last_price,
            "high": max(high_price, last_price, open_price if open_price > 0 else last_price),
            "low": min(low_price if low_price > 0 else last_price, last_price, open_price if open_price > 0 else last_price),
            "volume": volume,
            "amount": amount,
            "pct_chg": ((last_price / prev_close) - 1) * 100 if prev_close > 0 else 0.0,
        }
        merged = pd.concat([history, pd.DataFrame([synthetic_bar])], ignore_index=True)
        return self._finalize_daily_history_frame(merged, str(merged["date"].iloc[0]))

    def _persist_daily_history_rows(self, db: Session, symbol: str, history: pd.DataFrame) -> None:
        if history.empty:
            return
        rows = [
            DailyBarRow(
                trade_date=str(record["date"]),
                open_price=float(record["open"]),
                close_price=float(record["close"]),
                high_price=float(record["high"]),
                low_price=float(record["low"]),
                volume=float(record["volume"]),
                amount=float(record["amount"]),
                pct_chg=float(record["pct_chg"]),
            )
            for record in history.to_dict("records")
        ]
        DailyHistoryRepository(db).upsert_rows(symbol=symbol, payloads=rows)
        db.commit()

    def _finalize_daily_history_frame(self, normalized: pd.DataFrame | None, start_date_iso: str) -> pd.DataFrame | None:
        if normalized is None or normalized.empty:
            return None
        normalized = normalized.copy()
        normalized["date"] = normalized["date"].astype(str)
        normalized = normalized[normalized["date"] >= start_date_iso].copy()
        for column in ("open", "close", "high", "low", "volume", "amount", "pct_chg"):
            normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
        normalized = normalized.dropna(subset=["open", "close", "high", "low", "volume", "pct_chg"])
        if normalized.empty:
            return None
        normalized["ma5"] = normalized["close"].rolling(5).mean()
        normalized["ma10"] = normalized["close"].rolling(10).mean()
        normalized["ma20"] = normalized["close"].rolling(20).mean()
        normalized["ma60"] = normalized["close"].rolling(60).mean()
        return normalized.reset_index(drop=True)

    def _load_histories(
        self,
        items: list[BoardCandidate],
        latest_trade_date: str,
        active_trade_date: str | None = None,
        quote_map: dict[str, object] | None = None,
        wait_timeout_seconds: float | None = None,
    ) -> dict[str, pd.DataFrame | None]:
        if not items:
            return {}
        results: dict[str, pd.DataFrame | None] = {}
        max_workers = min(8 if len(items) > 120 else 6, len(items))
        history_wait_timeout = (
            max(float(wait_timeout_seconds), 1.0)
            if wait_timeout_seconds is not None
            else max(float(self.market_data.settings.http_timeout or 12), 12.0) * 2.0
        )
        executor = ThreadPoolExecutor(max_workers=max_workers)
        try:
            future_map = {executor.submit(self._load_daily_history, item.symbol, latest_trade_date): item.symbol for item in items}
            done, not_done = wait(future_map, timeout=history_wait_timeout)
            for future in done:
                symbol = future_map[future]
                try:
                    results[symbol] = future.result()
                except Exception:
                    results[symbol] = None
            if not_done:
                logger.warning(
                    "low-buy history load timed out after %.1fs for %d/%d symbols",
                    history_wait_timeout,
                    len(not_done),
                    len(items),
                )
                for future in not_done:
                    symbol = future_map[future]
                    results[symbol] = None
                    future.cancel()
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
        if active_trade_date and active_trade_date > latest_trade_date:
            for item in items:
                results[item.symbol] = self._build_intraday_history(results.get(item.symbol), active_trade_date=active_trade_date, quote=quote_map.get(item.symbol) if quote_map else None)
        return results

    @classmethod
    def _get_screen_cache(cls, cache_key: str):
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

    @classmethod
    def _set_screen_cache(cls, cache_key: str, payload, ttl: float | None = None) -> None:
        with cls._cache_lock:
            cls._screen_cache[cache_key] = (time.monotonic() + (ttl or cls._screen_cache_ttl), payload.model_copy(deep=True))

    @classmethod
    def _get_history_cache(cls, cache_key: str):
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

    @classmethod
    def _set_history_cache(cls, cache_key: str, payload: LowBuyHistoryResponse) -> None:
        with cls._cache_lock:
            cls._screen_cache[cache_key] = (time.monotonic() + cls._screen_cache_ttl, payload.model_copy(deep=True))

    @classmethod
    def _get_daily_history_cache(cls, cache_key: str):
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

    @classmethod
    def _set_daily_history_cache(cls, cache_key: str, payload: pd.DataFrame | None) -> None:
        with cls._cache_lock:
            cls._daily_history_cache[cache_key] = (time.monotonic() + cls._daily_history_cache_ttl, payload.copy(deep=True) if payload is not None else None)

    @classmethod
    def _get_spot_quote_cache(cls):
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

    @classmethod
    def _set_spot_quote_cache(cls, payload) -> None:
        with cls._cache_lock:
            cls._spot_quote_cache = (time.monotonic() + cls._spot_quote_cache_ttl, dict(payload))
