from __future__ import annotations

import logging
import threading
import time

from app.models.entities import LowBuyResultSnapshot, LowBuyScanSnapshot
from app.repositories.low_buy import LowBuyResultRepository, SystemSettingRepository
from app.services.low_buy.shared import (
    LOW_BUY_RESULT_VERSION,
    LowBuyCandidateOut,
    LowBuyScreenerResponse,
    Session,
    SessionLocal,
    json,
)
from app.services.low_buy.recommendation_duration import attach_response_recommendation_durations
from app.services.low_buy.strategy_policy import strong_buy_paused

logger = logging.getLogger(__name__)


class LowBuyResultStoreMixin:
    _confirmed_signal_states = ("buy_now", "soft_buy_now")

    def _make_screen_cache_key(
        self,
        strategy: str,
        latest_trade_date: str,
        limit: int,
        scan_limit: int,
        include_history: bool,
        scan_mode: str,
    ) -> str:
        if scan_mode == "full":
            return f"{strategy}:{latest_trade_date}:{limit}:mode=full:history={int(include_history)}"
        return f"{strategy}:{latest_trade_date}:{limit}:{scan_limit}:mode=quick:history={int(include_history)}"

    def _make_full_job_key(self, strategy: str, latest_trade_date: str, limit: int, include_history: bool) -> str:
        return f"{strategy}:{latest_trade_date}:{limit}:history={int(include_history)}"

    def _full_cache_setting_key(
        self,
        strategy: str,
        latest_trade_date: str,
        limit: int,
        include_history: bool,
    ) -> str:
        return f"{self._full_cache_setting_prefix}:{strategy}:{latest_trade_date}:{limit}:{int(include_history)}"

    def _resolve_full_scan_limit(self, requested_scan_limit: int) -> int:
        return max(requested_scan_limit, self._default_full_scan_limit)

    def _load_cached_full_result(
        self,
        db: Session,
        strategy: str,
        latest_trade_date: str,
        limit: int,
        include_history: bool,
    ) -> LowBuyScreenerResponse | None:
        cache_key = self._make_screen_cache_key(
            strategy=strategy,
            latest_trade_date=latest_trade_date,
            limit=limit,
            scan_limit=self._default_full_scan_limit,
            include_history=include_history,
            scan_mode="full",
        )
        cached_full = self._get_screen_cache(cache_key)
        if cached_full is not None:
            cached_full = self._normalize_response_candidate_policy_state(cached_full)
            return attach_response_recommendation_durations(db=db, payload=cached_full)

        materialized = self._load_materialized_full_result(
            db=db,
            strategy=strategy,
            latest_trade_date=latest_trade_date,
            limit=limit,
            include_history=include_history,
        )
        if materialized is not None:
            materialized = attach_response_recommendation_durations(db=db, payload=materialized)
            self._set_screen_cache(cache_key, materialized, ttl=self._screen_cache_ttl_full)
            return materialized.model_copy(deep=True)

        setting_key = self._full_cache_setting_key(strategy, latest_trade_date, limit, include_history)
        row = SystemSettingRepository(db).fetch(setting_key)
        if row is None or not row.value:
            return None
        if not self._response_payload_is_current(row.value):
            return None
        try:
            payload = LowBuyScreenerResponse.model_validate_json(row.value)
        except Exception:
            return None
        payload = self._normalize_response_candidate_policy_state(payload)
        payload = attach_response_recommendation_durations(db=db, payload=payload)
        self._set_screen_cache(cache_key, payload, ttl=self._screen_cache_ttl_full)
        return payload.model_copy(deep=True)

    def _load_latest_materialized_full_result(
        self,
        db: Session,
        strategy: str,
        limit: int,
        include_history: bool,
        allow_repair: bool = False,
    ) -> LowBuyScreenerResponse | None:
        repository = LowBuyResultRepository(db)
        summary = repository.fetch_latest_scan_summary(strategy_key=strategy)
        if summary is not None:
            payload = self._load_materialized_full_result(
                db=db,
                strategy=strategy,
                latest_trade_date=summary.latest_trade_date,
                limit=limit,
                include_history=include_history,
            )
            if payload is not None:
                return payload
            if allow_repair:
                repaired = self._repair_materialized_snapshot(
                    db=db,
                    strategy=strategy,
                    latest_trade_date=str(summary.latest_trade_date),
                    limit=limit,
                    include_history=include_history,
                )
                if repaired is not None:
                    return repaired

        for fallback in repository.fetch_recent_scan_summaries(strategy_key=strategy, limit=8):
            if summary is not None and fallback.id == summary.id:
                continue
            payload = self._load_materialized_full_result(
                db=db,
                strategy=strategy,
                latest_trade_date=fallback.latest_trade_date,
                limit=limit,
                include_history=include_history,
            )
            if payload is not None:
                return payload
        return None

    def _repair_materialized_snapshot(
        self,
        db: Session,
        strategy: str,
        latest_trade_date: str,
        limit: int,
        include_history: bool,
    ) -> LowBuyScreenerResponse | None:
        repair = getattr(self, "_rebuild_materialized_snapshot", None)
        if repair is None or not latest_trade_date:
            return None
        try:
            return repair(
                db=db,
                strategy=strategy,
                latest_trade_date=latest_trade_date,
                limit=limit,
                include_history=include_history,
            )
        except Exception:
            return None

    def _save_persisted_full_result(
        self,
        db: Session,
        payload: LowBuyScreenerResponse,
        limit: int,
        include_history: bool,
    ) -> None:
        self._persist_materialized_full_result(db=db, payload=payload)
        db.commit()

    def _persist_materialized_full_result(self, db: Session, payload: LowBuyScreenerResponse) -> None:
        summary = LowBuyScanSnapshot(
            latest_trade_date=payload.latest_trade_date,
            strategy_key=payload.strategy_key,
            strategy_title=payload.strategy_title,
            strategy_subtitle=payload.strategy_subtitle,
            strategy_logic=payload.strategy_logic,
            as_of_date=payload.as_of_date,
            pool_size=payload.pool_size,
            scanned_count=payload.scanned_count,
            matched_count=payload.matched_count,
            requested_scan_limit=payload.requested_scan_limit,
            active_scan_limit=payload.active_scan_limit,
            retracement_distribution_json=json.dumps(payload.retracement_distribution, ensure_ascii=False),
            filters_json=json.dumps(payload.filters, ensure_ascii=False),
            strategy_notes_json=json.dumps(payload.strategy_notes, ensure_ascii=False),
        )
        results = [
            LowBuyResultSnapshot(
                latest_trade_date=payload.latest_trade_date,
                strategy_key=payload.strategy_key,
                symbol=candidate.symbol,
                name=candidate.name,
                score=candidate.score,
                buy_signal_state=candidate.buy_signal_state,
                payload_json=candidate.model_dump_json(),
            )
            for candidate in payload.confirmed_candidates + payload.candidates
        ]
        LowBuyResultRepository(db).replace_materialized_scan(
            latest_trade_date=payload.latest_trade_date,
            strategy_key=payload.strategy_key,
            summary=summary,
            results=results,
        )

    def _load_materialized_full_result(
        self,
        db: Session,
        strategy: str,
        latest_trade_date: str,
        limit: int,
        include_history: bool,
    ) -> LowBuyScreenerResponse | None:
        summary = LowBuyResultRepository(db).fetch_scan_summary(
            latest_trade_date=latest_trade_date,
            strategy_key=strategy,
        )
        if summary is None or not self._materialized_scan_is_current(
            db=db,
            strategy=strategy,
            latest_trade_date=latest_trade_date,
            summary=summary,
        ):
            return None
        summary_filters = self._safe_json_object(summary.filters_json)
        rows = LowBuyResultRepository(db).fetch_results(
            latest_trade_date=latest_trade_date,
            strategy_key=strategy,
        )
        candidates = self._deserialize_candidates(rows) if rows else []

        dedupe_candidates = getattr(self, "_dedupe_candidates", _dedupe_candidates_by_symbol)
        signal_rank = getattr(self, "_signal_rank", _default_signal_rank)
        candidates = dedupe_candidates(candidates)
        candidates.sort(key=lambda item: (signal_rank(item.buy_signal_state), item.score), reverse=True)
        confirmed_candidates = [
            item for item in candidates if item.buy_signal_state in self._confirmed_signal_states
        ][:12]
        watch_candidates = [
            item for item in candidates if item.buy_signal_state not in self._confirmed_signal_states
        ][:limit]
        history_sections = []
        if include_history and strategy == "classic_retrace":
            completed_trade_dates = [item for item in self._get_recent_trade_dates(14) if item <= latest_trade_date]
            history_sections = self._build_history_sections(
                completed_trade_dates[-4:-1],
                strategy,
                db=db,
            )

        payload = LowBuyScreenerResponse(
            strategy_key=summary.strategy_key,
            strategy_title=summary.strategy_title,
            strategy_subtitle=summary.strategy_subtitle,
            strategy_logic=summary.strategy_logic,
            requested_mode="full",
            response_mode="full",
            as_of_date=summary.as_of_date,
            latest_trade_date=summary.latest_trade_date,
            pool_size=summary.pool_size,
            scanned_count=summary.scanned_count,
            matched_count=summary.matched_count,
            requested_scan_limit=summary.requested_scan_limit,
            active_scan_limit=summary.active_scan_limit,
            full_scan_ready=True,
            full_scan_in_progress=False,
            full_scan_updated_at=summary.as_of_date,
            market_state=str(summary_filters.get("market_state") or "low_volume_wait"),
            market_state_text=str(summary_filters.get("market_regime") or ""),
            market_bonus=float(summary_filters.get("market_bonus") or 0.0),
            market_state_strength=float(summary_filters.get("market_state_strength") or 0.0),
            regime_confidence=float(summary_filters.get("regime_confidence") or 0.0),
            state_persistence_days=int(summary_filters.get("state_persistence_days") or 1),
            transition_risk=float(summary_filters.get("transition_risk") or 0.0),
            breadth_ready=bool(summary_filters.get("breadth_ready") or False),
            emotion_ready=bool(summary_filters.get("emotion_ready") or False),
            stock_up_ratio=float(summary_filters.get("stock_up_ratio") or 0.0),
            stock_median_change=float(summary_filters.get("stock_median_change") or 0.0),
            style_divergence=float(summary_filters.get("style_divergence") or 0.0),
            hot_turnover=float(summary_filters.get("hot_turnover") or 0.0),
            hot_overlap_ratio=float(summary_filters.get("hot_overlap_ratio") or 0.0),
            limit_down_count=int(summary_filters.get("limit_down_count")) if str(summary_filters.get("limit_down_count") or "").isdigit() else None,
            limit_up_count=int(summary_filters.get("limit_up_count") or 0),
            board_height=int(summary_filters.get("board_height") or 0),
            previous_board_height=int(summary_filters.get("previous_board_height") or 0),
            promotion_ratio=float(summary_filters.get("promotion_ratio") or 0.0),
            broken_board_ratio=float(summary_filters.get("broken_board_ratio") or 0.0),
            promotion_break_gap=float(summary_filters.get("promotion_break_gap") or 0.0),
            promotion_break_pressure=float(summary_filters.get("promotion_break_pressure") or 0.0),
            high_flyer_retreat_ratio=float(summary_filters.get("high_flyer_retreat_ratio") or 0.0),
            high_flyer_gap_speed=float(summary_filters.get("high_flyer_gap_speed") or 0.0),
            distribution_pressure=float(summary_filters.get("distribution_pressure") or 0.0),
            hot_industries=self._safe_json_list(summary_filters.get("hot_industries_json", "[]"))
            or [item.strip() for item in str(summary_filters.get("hot_industries") or "").split("/") if item.strip()],
            hot_industry_source=str(summary_filters.get("hot_industry_source") or ""),
            hot_industry_source_text=str(summary_filters.get("hot_industry_source_text") or ""),
            mainline_lifecycle_state=str(summary_filters.get("mainline_lifecycle_state") or ""),
            mainline_lifecycle_text=str(summary_filters.get("mainline_lifecycle_text") or ""),
            retracement_distribution=self._safe_json_object(summary.retracement_distribution_json),
            filters=summary_filters,
            strategy_notes=self._safe_json_list(summary.strategy_notes_json),
            confirmed_candidates=confirmed_candidates,
            history_sections=history_sections,
            candidates=watch_candidates,
        )
        return attach_response_recommendation_durations(db=db, payload=payload)

    def _deserialize_candidates(self, rows: list[LowBuyResultSnapshot]) -> list[LowBuyCandidateOut]:
        candidates: list[LowBuyCandidateOut] = []
        for row in rows:
            if not self._candidate_payload_is_current(row.payload_json):
                continue
            try:
                candidate = LowBuyCandidateOut.model_validate_json(row.payload_json)
            except Exception:
                continue
            candidates.append(self._normalize_candidate_policy_state(candidate))
        return candidates

    def _load_materialized_candidates_by_symbol(
        self,
        db: Session,
        strategy: str,
        latest_trade_date: str,
        symbols: list[str],
    ) -> dict[str, LowBuyCandidateOut]:
        if not symbols:
            return {}
        if not self._materialized_scan_is_current(
            db=db,
            strategy=strategy,
            latest_trade_date=latest_trade_date,
        ):
            return {}
        rows = LowBuyResultRepository(db).fetch_results_for_symbols(
            latest_trade_date=latest_trade_date,
            strategy_key=strategy,
            symbols=symbols,
        )
        performance = self._load_strategy_performance_snapshot(
            db=db,
            strategy=strategy,
            latest_trade_date=latest_trade_date,
        )
        result: dict[str, LowBuyCandidateOut] = {}
        for row in rows:
            if not self._candidate_payload_is_current(row.payload_json):
                continue
            try:
                candidate = LowBuyCandidateOut.model_validate_json(row.payload_json)
            except Exception:
                continue
            candidate = self._normalize_candidate_policy_state(candidate)
            result[row.symbol] = self._apply_candidate_positioning(candidate, performance)
        return result

    @staticmethod
    def _normalize_candidate_policy_state(candidate: LowBuyCandidateOut) -> LowBuyCandidateOut:
        if not strong_buy_paused(candidate.strategy_key):
            return candidate
        if candidate.buy_signal_state not in {"buy_now", "soft_buy_now"}:
            return candidate
        return candidate.model_copy(
            update={
                "buy_signal_state": "near_entry",
                "buy_signal_text": "接近买点",
                "buy_signal_hint": "该策略当前处于观察层，只保留接近买点提醒，不再给确定买入信号。",
            }
        )

    def _normalize_response_candidate_policy_state(
        self,
        payload: LowBuyScreenerResponse,
    ) -> LowBuyScreenerResponse:
        candidates = [
            self._normalize_candidate_policy_state(candidate)
            for candidate in payload.confirmed_candidates + payload.candidates
        ]
        candidates = self._dedupe_candidates(candidates)
        candidates.sort(key=lambda item: (self._signal_rank(item.buy_signal_state), item.score), reverse=True)
        confirmed_candidates = [
            item for item in candidates if item.buy_signal_state in self._confirmed_signal_states
        ][:12]
        watch_candidates = [
            item for item in candidates if item.buy_signal_state not in self._confirmed_signal_states
        ][: len(payload.candidates) or 16]
        return payload.model_copy(
            update={
                "confirmed_candidates": confirmed_candidates,
                "candidates": watch_candidates,
            }
        )

    def _materialized_scan_is_current(
        self,
        db: Session,
        strategy: str,
        latest_trade_date: str,
        summary: LowBuyScanSnapshot | None = None,
    ) -> bool:
        summary = summary or LowBuyResultRepository(db).fetch_scan_summary(
            latest_trade_date=latest_trade_date,
            strategy_key=strategy,
        )
        if summary is None:
            return False
        if int(summary.pool_size or 0) <= 0 or int(summary.active_scan_limit or 0) <= 0:
            return False
        summary_filters = self._safe_json_object(summary.filters_json)
        if not self._summary_filters_are_current(summary_filters):
            return False
        rows = LowBuyResultRepository(db).fetch_results(
            latest_trade_date=latest_trade_date,
            strategy_key=strategy,
        )
        if not rows:
            return True
        return all(self._candidate_payload_is_current(row.payload_json) for row in rows)

    @staticmethod
    def _safe_json_object(raw: str | dict | None) -> dict:
        if isinstance(raw, dict):
            return raw
        try:
            payload = json.loads(raw or "{}")
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _safe_json_list(raw: str | list | None) -> list:
        if isinstance(raw, list):
            return raw
        try:
            payload = json.loads(raw or "[]")
        except Exception:
            return []
        return payload if isinstance(payload, list) else []

    def _response_payload_is_current(self, payload_source: str | dict) -> bool:
        payload = self._load_json_object(payload_source)
        if payload is None or not self._summary_filters_are_current(payload.get("filters")):
            return False
        candidates = list(payload.get("confirmed_candidates") or []) + list(payload.get("candidates") or [])
        history_sections = payload.get("history_sections") or []
        for section in history_sections:
            if not isinstance(section, dict):
                return False
            candidates.extend(section.get("candidates") or [])
        return all(self._candidate_payload_is_current(candidate) for candidate in candidates)

    @staticmethod
    def _summary_filters_are_current(summary_filters: dict | None) -> bool:
        required_keys = (
            "market_regime",
            "market_state",
            "market_state_strength",
            "regime_confidence",
            "state_persistence_days",
            "transition_risk",
            "breadth_ready",
            "emotion_ready",
            "market_bonus",
            "hot_industries_json",
            "hot_industry_source",
            "hot_industry_source_text",
            "limit_up_count",
            "board_height",
            "promotion_ratio",
            "broken_board_ratio",
            "high_flyer_retreat_ratio",
            "stock_up_ratio",
            "stock_median_change",
            "style_divergence",
            "hot_turnover",
            "hot_overlap_ratio",
            "previous_board_height",
            "promotion_break_gap",
            "promotion_break_pressure",
            "high_flyer_gap_speed",
            "distribution_pressure",
            "mainline_lifecycle_state",
            "mainline_lifecycle_text",
            "structure_mode",
        )
        return (
            isinstance(summary_filters, dict)
            and summary_filters.get("_result_version") == LOW_BUY_RESULT_VERSION
            and all(key in summary_filters for key in required_keys)
        )

    @staticmethod
    def _load_json_object(payload_source: str | dict) -> dict | None:
        if isinstance(payload_source, dict):
            return payload_source
        try:
            payload = json.loads(payload_source or "{}")
        except Exception:
            return None
        return payload if isinstance(payload, dict) else None

    @staticmethod
    def _candidate_payload_is_current(payload_source: str | dict) -> bool:
        payload = LowBuyResultStoreMixin._load_json_object(payload_source)
        if payload is None:
            return False
        required_keys = (
            "payload_version",
            "market_state",
            "industry_tier",
            "risk_position_multiplier",
            "market_position_multiplier",
            "industry_position_multiplier",
            "dynamic_position_multiplier",
            "distribution_risk_score",
            "risk_tier",
            "false_breakout_flag",
            "stall_after_volume_flag",
            "intraday_reversal_flag",
            "dynamic_threshold_adjustment",
            "hard_risk",
            "exit_plan",
            "next_day_event_plan",
            "research_stage",
            "research_failed_rules",
            "research_near_miss_rules",
        )
        if payload.get("payload_version") != LOW_BUY_RESULT_VERSION:
            return False
        if not all(key in payload for key in required_keys):
            return False
        try:
            LowBuyCandidateOut.model_validate(payload)
        except Exception:
            return False
        return True

    def _is_full_scan_running(
        self,
        strategy: str,
        latest_trade_date: str,
        limit: int,
        include_history: bool,
    ) -> bool:
        job_key = self._make_full_job_key(strategy, latest_trade_date, limit, include_history)
        now = time.monotonic()
        with self._cache_lock:
            expires_at = self._full_scan_jobs.get(job_key)
            if expires_at is None:
                return False
            if expires_at <= now:
                self._full_scan_jobs.pop(job_key, None)
                return False
            return True

    def _ensure_background_full_scan(
        self,
        strategy: str,
        latest_trade_date: str,
        limit: int,
        scan_limit: int,
        include_history: bool,
        compute_performance: bool = True,
        build_close_review: bool = True,
    ) -> bool:
        job_key = self._make_full_job_key(strategy, latest_trade_date, limit, include_history)
        now = time.monotonic()
        with self._cache_lock:
            for active_key, expires_at in list(self._full_scan_jobs.items()):
                if expires_at <= now:
                    self._full_scan_jobs.pop(active_key, None)
            expires_at = self._full_scan_jobs.get(job_key)
            if expires_at is not None and expires_at > now:
                return True
            if self._full_scan_jobs:
                return True
            self._full_scan_jobs[job_key] = now + 600.0

        def runner() -> None:
            try:
                self.refresh_full_scan_cache(
                    strategy=strategy,
                    limit=limit,
                    scan_limit=scan_limit,
                    include_history=include_history,
                    compute_performance=compute_performance,
                    build_close_review=build_close_review,
                )
            except Exception:
                logger.exception("low-buy background full scan failed")
            finally:
                with self._cache_lock:
                    self._full_scan_jobs.pop(job_key, None)

        # Defer the heavy scan very slightly so the HTTP request can return the
        # cached/pending response instead of competing with the worker thread.
        thread = threading.Timer(0.2, runner)
        thread.name = f"low-buy-full-{strategy}"
        thread.daemon = True
        thread.start()
        return True


def _default_signal_rank(state: str) -> int:
    return {"buy_now": 4, "soft_buy_now": 3, "near_entry": 2, "watch": 1}.get(state, 0)


def _dedupe_candidates_by_symbol(items: list[LowBuyCandidateOut]) -> list[LowBuyCandidateOut]:
    seen: set[str] = set()
    result: list[LowBuyCandidateOut] = []
    for item in items:
        if item.symbol in seen:
            continue
        seen.add(item.symbol)
        result.append(item)
    return result
