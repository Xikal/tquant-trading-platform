from __future__ import annotations

import time

from app.models.entities import LowBuyResultSnapshot, LowBuyScanSnapshot
from app.repositories.low_buy import LowBuyResultRepository, SystemSettingRepository
from app.services.low_buy.shared import (
    LowBuyCandidateOut,
    LowBuyScreenerResponse,
    Session,
    SessionLocal,
    json,
)
from app.services.low_buy.recommendation_duration import attach_response_recommendation_durations
from app.services.low_buy.result_materialized import (
    deserialize_candidates,
    load_materialized_candidates_by_symbol,
    load_materialized_full_result,
)
from app.services.low_buy.result_payloads import (
    candidate_payload_is_current,
    load_json_object,
    normalize_candidate_policy_state,
    response_payload_is_current,
    safe_json_list,
    safe_json_object,
    summary_filters_are_current,
)

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

    def _load_latest_materialized_full_result_on_or_before(
        self,
        db: Session,
        strategy: str,
        latest_trade_date: str,
        limit: int,
        include_history: bool,
        allow_repair: bool = False,
    ) -> LowBuyScreenerResponse | None:
        if not latest_trade_date:
            return self._load_latest_materialized_full_result(
                db=db,
                strategy=strategy,
                limit=limit,
                include_history=include_history,
                allow_repair=allow_repair,
            )

        repository = LowBuyResultRepository(db)
        summary = repository.fetch_latest_scan_summary_on_or_before(
            strategy_key=strategy,
            latest_trade_date=latest_trade_date,
        )
        if summary is None:
            return None

        summaries = [summary]
        summaries.extend(
            item
            for item in repository.fetch_recent_scan_summaries(strategy_key=strategy, limit=8)
            if item.id != summary.id and str(item.latest_trade_date) <= latest_trade_date
        )
        for item in summaries:
            payload = self._load_materialized_full_result(
                db=db,
                strategy=strategy,
                latest_trade_date=str(item.latest_trade_date),
                limit=limit,
                include_history=include_history,
            )
            if payload is not None:
                return payload
            if allow_repair and item.id == summary.id:
                repaired = self._repair_materialized_snapshot(
                    db=db,
                    strategy=strategy,
                    latest_trade_date=str(item.latest_trade_date),
                    limit=limit,
                    include_history=include_history,
                )
                if repaired is not None:
                    return repaired
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
        repair_db = SessionLocal()
        try:
            payload = repair(
                db=repair_db,
                strategy=strategy,
                latest_trade_date=latest_trade_date,
                limit=limit,
                include_history=include_history,
            )
            if payload is None:
                repair_db.rollback()
                return None
            repair_db.commit()
            return payload
        except Exception:
            repair_db.rollback()
            return None
        finally:
            repair_db.close()

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
        return load_materialized_full_result(
            self,
            db=db,
            strategy=strategy,
            latest_trade_date=latest_trade_date,
            limit=limit,
            include_history=include_history,
        )

    def _deserialize_candidates(self, rows: list[LowBuyResultSnapshot]) -> list[LowBuyCandidateOut]:
        return deserialize_candidates(self, rows)

    def _load_materialized_candidates_by_symbol(
        self,
        db: Session,
        strategy: str,
        latest_trade_date: str,
        symbols: list[str],
    ) -> dict[str, LowBuyCandidateOut]:
        return load_materialized_candidates_by_symbol(
            self,
            db=db,
            strategy=strategy,
            latest_trade_date=latest_trade_date,
            symbols=symbols,
        )

    @staticmethod
    def _normalize_candidate_policy_state(candidate: LowBuyCandidateOut) -> LowBuyCandidateOut:
        return normalize_candidate_policy_state(candidate)

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
        return safe_json_object(raw)

    @staticmethod
    def _safe_json_list(raw: str | list | None) -> list:
        return safe_json_list(raw)

    def _response_payload_is_current(self, payload_source: str | dict) -> bool:
        return response_payload_is_current(payload_source)

    @staticmethod
    def _summary_filters_are_current(summary_filters: dict | None) -> bool:
        return summary_filters_are_current(summary_filters)

    @staticmethod
    def _load_json_object(payload_source: str | dict) -> dict | None:
        return load_json_object(payload_source)

    @staticmethod
    def _candidate_payload_is_current(payload_source: str | dict) -> bool:
        return candidate_payload_is_current(payload_source)

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
