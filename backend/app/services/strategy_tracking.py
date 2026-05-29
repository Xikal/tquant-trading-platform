from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Iterable

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.entities import Instrument, LowBuyResultSnapshot, LowBuyTradeLifecycleSnapshot, MarketModelObservation
from app.models.schema_defs.strategy_tracking import (
    StrategyTrackingDetailResponse,
    StrategyTrackingHoldingAnalysisResponse,
    StrategyTrackingItemOut,
    StrategyTrackingListResponse,
    StrategyTrackingPerformanceOut,
    StrategyTrackingReportOut,
    StrategyTrackingReviewResponse,
    StrategyTrackingRefreshResponse,
    StrategyTrackingShadowObservationOut,
    StrategyTrackingSummaryOut,
)
from app.repositories.low_buy import DailyBarRow, DailyHistoryRepository
from app.services.low_buy.strategy_policy import get_strategy_tier, participates_in_priority_board
from app.services.strategy_metadata_service import StrategyMetadataService
from app.services.strategy_tracking_constants import (
    DEFAULT_LIMIT,
    DEFAULT_RANGE_DAYS,
    MAX_LIMIT,
    TRACKED_SIGNAL_STATES,
)
from app.services.strategy_tracking_builders import build_markers, build_timeline, build_tracking_item
from app.services.strategy_tracking_filters import filter_items, sort_items
from app.services.strategy_tracking_helpers import (
    build_performance,
    build_market_segments,
    build_summary,
    compact_payload,
    failure_tag_counts,
    load_payload,
    parse_item_id,
    text,
)
from app.services.strategy_tracking_reports import (
    build_shadow_row,
    calendar_lookback,
    report_markdown,
)
from app.services.strategy_tracking_usability import build_holding_analysis

logger = logging.getLogger(__name__)
_READ_MODEL_CACHE_TTL_SECONDS = 20.0
_READ_MODEL_CACHE_MAX_SIZE = 16
_READ_MODEL_CACHE_LOCK = threading.Lock()
_READ_MODEL_CACHE: dict[tuple[object, ...], tuple[float, list[StrategyTrackingItemOut], list[str]]] = {}


def clear_strategy_tracking_read_cache() -> None:
    with _READ_MODEL_CACHE_LOCK:
        _READ_MODEL_CACHE.clear()


def _get_read_model_cache(cache_key: tuple[object, ...]) -> tuple[list[StrategyTrackingItemOut], list[str]] | None:
    now = time.monotonic()
    with _READ_MODEL_CACHE_LOCK:
        cached = _READ_MODEL_CACHE.get(cache_key)
        if cached is None:
            return None
        expires_at, items, partial_errors = cached
        if expires_at <= now:
            _READ_MODEL_CACHE.pop(cache_key, None)
            return None
        return list(items), list(partial_errors)


def _set_read_model_cache(
    cache_key: tuple[object, ...],
    payload: tuple[list[StrategyTrackingItemOut], list[str]],
) -> None:
    now = time.monotonic()
    expires_at = now + _READ_MODEL_CACHE_TTL_SECONDS
    with _READ_MODEL_CACHE_LOCK:
        for key, (cached_expires_at, _items, _errors) in list(_READ_MODEL_CACHE.items()):
            if cached_expires_at <= now:
                _READ_MODEL_CACHE.pop(key, None)
        while len(_READ_MODEL_CACHE) >= _READ_MODEL_CACHE_MAX_SIZE:
            oldest_key = next(iter(_READ_MODEL_CACHE))
            _READ_MODEL_CACHE.pop(oldest_key, None)
        items, partial_errors = payload
        _READ_MODEL_CACHE[cache_key] = (expires_at, list(items), list(partial_errors))


@dataclass(frozen=True)
class TrackingGroup:
    strategy_key: str
    symbol: str
    rows: tuple[LowBuyResultSnapshot, ...]
    latest_row: LowBuyResultSnapshot
    first_row: LowBuyResultSnapshot
    payload: dict[str, Any]
    payload_error: str | None = None


class StrategyTrackingService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_items(
        self,
        *,
        range_days: int = DEFAULT_RANGE_DAYS,
        strategy_key: str | None = None,
        strategy_family: str | None = None,
        lifecycle_status: str | None = None,
        signal_state: str | None = None,
        data_quality: str | None = None,
        hit_entry: bool | None = None,
        stopped: bool | None = None,
        exclude_chinext: bool = False,
        exclude_star: bool = False,
        board_filter: str | None = None,
        user_status: str | None = None,
        sort: str = "max_gain_desc",
        limit: int = DEFAULT_LIMIT,
        offset: int = 0,
    ) -> StrategyTrackingListResponse:
        safe_limit = max(1, min(limit, MAX_LIMIT))
        safe_offset = max(0, offset)
        all_items, partial_errors = self._load_read_model(
            range_days=range_days,
            strategy_key=strategy_key,
            strategy_family=strategy_family,
        )
        if signal_state:
            all_items = [item for item in all_items if item.signal_state == signal_state]
        items = filter_items(
            all_items,
            lifecycle_status=lifecycle_status,
            data_quality=data_quality,
            hit_entry=hit_entry,
            stopped=stopped,
            exclude_chinext=exclude_chinext,
            exclude_star=exclude_star,
            board_filter=board_filter,
            user_status=user_status,
        )
        items = sort_items(items, sort=sort)
        total = len(items)
        page_items = items[safe_offset : safe_offset + safe_limit]
        summary = build_summary(items)
        performance = build_performance(items)
        market_segments = build_market_segments(items)
        shadow = self.shadow_observations(range_days=range_days, items=all_items)
        summary.shadow_observation_count = sum(item.observation_count for item in shadow)
        return StrategyTrackingListResponse(
            items=page_items,
            total=total,
            limit=safe_limit,
            offset=safe_offset,
            sort=sort,
            summary=summary,
            performance=performance,
            market_segments=market_segments,
            shadow_observations=shadow,
            partial_errors=partial_errors,
            notes=[
                "后验表现仅使用首次推荐日之后的行情，不回写策略分数或交易账本。",
                "Go 读聚合边界预留为 /bff/v1/workspace/strategy-tracking。",
                "最大回撤通过 Rust wrapper 优先计算，失败自动回退 Python。",
            ],
        )

    def summary(
        self,
        *,
        range_days: int = DEFAULT_RANGE_DAYS,
        strategy_key: str | None = None,
        strategy_family: str | None = None,
        lifecycle_status: str | None = None,
    ) -> StrategyTrackingSummaryOut:
        result = self.list_items(
            range_days=range_days,
            strategy_key=strategy_key,
            strategy_family=strategy_family,
            lifecycle_status=lifecycle_status,
            limit=1,
        )
        return result.summary

    def performance(
        self,
        *,
        range_days: int = DEFAULT_RANGE_DAYS,
        strategy_family: str | None = None,
    ) -> list[StrategyTrackingPerformanceOut]:
        result = self.list_items(range_days=range_days, strategy_family=strategy_family, limit=1)
        return result.performance

    def holding_analysis(
        self,
        *,
        range_days: int = DEFAULT_RANGE_DAYS,
        strategy_family: str | None = None,
        exclude_chinext: bool = False,
        exclude_star: bool = False,
        board_filter: str | None = None,
    ) -> StrategyTrackingHoldingAnalysisResponse:
        result = self.list_items(
            range_days=range_days,
            strategy_family=strategy_family,
            exclude_chinext=exclude_chinext,
            exclude_star=exclude_star,
            board_filter=board_filter,
            limit=MAX_LIMIT,
        )
        return StrategyTrackingHoldingAnalysisResponse(
            items=build_holding_analysis(result.items),
            generated_at=result.summary.generated_at,
            data_quality=result.summary.data_quality,
            production_writeable=False,
        )

    def review(
        self,
        *,
        range_days: int = DEFAULT_RANGE_DAYS,
        strategy_key: str | None = None,
        strategy_family: str | None = None,
    ) -> StrategyTrackingReviewResponse:
        result = self.list_items(
            range_days=range_days,
            strategy_key=strategy_key,
            strategy_family=strategy_family,
            limit=MAX_LIMIT,
        )
        return StrategyTrackingReviewResponse(
            summary=result.summary,
            performance=result.performance,
            market_segments=result.market_segments,
            failure_tags=failure_tag_counts(result.items),
            needs_review_items=[item for item in result.items if item.needs_review][:20],
            abnormal_return_items=[item for item in result.items if item.abnormal_return][:20],
        )

    def market_segments(self, *, range_days: int = DEFAULT_RANGE_DAYS, strategy_family: str | None = None):
        result = self.list_items(range_days=range_days, strategy_family=strategy_family, limit=1)
        return result.market_segments

    def shadow_observations(
        self,
        *,
        range_days: int = DEFAULT_RANGE_DAYS,
        model_key: str | None = None,
        strategy_key: str | None = None,
        items: list[StrategyTrackingItemOut] | None = None,
    ) -> list[StrategyTrackingShadowObservationOut]:
        keys = [model_key] if model_key else ["main_force_model_observation", "sector_etf_t0", "paper_exit_model"]
        tracking_items = items
        if tracking_items is None:
            tracking_items = self.list_items(range_days=range_days, strategy_key=strategy_key, limit=MAX_LIMIT).items
        start_date = self._range_start_date(range_days)
        rows: list[StrategyTrackingShadowObservationOut] = []
        for key in keys:
            statement = select(MarketModelObservation).where(MarketModelObservation.model_key == key)
            if start_date:
                statement = statement.where(MarketModelObservation.trade_date >= start_date)
            observations = self.db.execute(statement.order_by(MarketModelObservation.observed_at.desc())).scalars().all()
            rows.append(build_shadow_row(model_key=key, observations=observations, tracking_items=tracking_items))
        return rows

    def leakage_audit(
        self,
        *,
        range_days: int = DEFAULT_RANGE_DAYS,
        strategy_key: str | None = None,
        needs_review: bool | None = None,
        abnormal_return: bool | None = None,
    ) -> StrategyTrackingReviewResponse:
        result = self.list_items(range_days=range_days, strategy_key=strategy_key, limit=MAX_LIMIT)
        items = result.items
        if needs_review is not None:
            items = [item for item in items if item.needs_review == needs_review]
        if abnormal_return is not None:
            items = [item for item in items if item.abnormal_return == abnormal_return]
        return StrategyTrackingReviewResponse(
            summary=build_summary(items),
            performance=build_performance(items),
            market_segments=build_market_segments(items),
            failure_tags=failure_tag_counts(items),
            needs_review_items=[item for item in items if item.needs_review][:50],
            abnormal_return_items=[item for item in items if item.abnormal_return][:50],
        )

    def report(self, *, report_type: str = "daily", range_days: int = 7) -> StrategyTrackingReportOut:
        result = self.list_items(range_days=range_days, limit=MAX_LIMIT)
        items = result.items
        window_start = min((item.first_signal_date for item in items), default="")
        window_end = max((item.latest_trade_date or item.latest_signal_date for item in items), default="")
        shadow = result.shadow_observations
        markdown = report_markdown(report_type=report_type, summary=result.summary, items=items, shadow=shadow)
        return StrategyTrackingReportOut(
            report_type=report_type,
            generated_at=result.summary.generated_at,
            window_start=window_start,
            window_end=window_end,
            data_quality=result.summary.data_quality,
            summary=result.summary,
            new_signals=[item for item in items if item.first_signal_date == item.latest_signal_date][:20],
            entry_touched=[item for item in items if item.entry_touched][:20],
            stopped=[item for item in items if item.stop_triggered][:20],
            spike_retraced=[item for item in items if "spike_without_take_profit" in item.failure_tags][:20],
            abnormal_returns=[item for item in items if item.abnormal_return][:20],
            shadow_observations=shadow,
            markdown=markdown,
        )

    def detail(self, item_id: str) -> StrategyTrackingDetailResponse:
        strategy_key, symbol, first_signal_date = parse_item_id(item_id)
        groups, partial_errors = self._load_groups(range_days=260, strategy_key=strategy_key)
        group = next(
            (
                item
                for item in groups
                if item.symbol == symbol and self._first_signal_date(item) == first_signal_date
            ),
            None,
        )
        if group is None:
            raise LookupError("未找到策略跟踪记录")
        latest_bar_date = self._latest_bar_date()
        bars = self._fetch_bars([group], latest_bar_date=latest_bar_date).get(symbol, [])
        lifecycle = self._load_lifecycles([group]).get(self._group_key(group))
        instrument_payload = self._load_instrument_payloads([group]).get(symbol)
        item = self._build_item(group, bars, lifecycle, latest_bar_date, instrument_payload=instrument_payload)
        timeline = build_timeline(bars=bars, item=item)
        markers = build_markers(item=item, timeline=timeline)
        return StrategyTrackingDetailResponse(
            item=item,
            timeline=timeline,
            markers=markers,
            signal_snapshot=compact_payload(group.payload),
            review_text=item.review_text,
            partial_errors=[item for item in partial_errors if item],
        )

    def refresh(self, *, range_days: int = DEFAULT_RANGE_DAYS) -> StrategyTrackingRefreshResponse:
        result = self.list_items(range_days=range_days, limit=1)
        return StrategyTrackingRefreshResponse(
            storage_mode="read_through_view_no_strategy_write",
            refreshed_count=result.summary.tracking_count,
            changed_strategy_results=False,
            changed_paper_ledger=False,
            summary=result.summary,
        )

    def _load_groups(
        self,
        *,
        range_days: int,
        strategy_key: str | None,
    ) -> tuple[list[TrackingGroup], list[str]]:
        dates = self._recent_result_dates(range_days)
        return self._load_groups_for_dates(result_dates=dates, strategy_key=strategy_key)

    def _production_strategy_keys(self) -> set[str]:
        try:
            items = StrategyMetadataService(self.db).list_strategy_meta().strategies
            keys = {
                item.key
                for item in items
                if item.enabled and item.visibility == "full" and item.category_key in {"core", "auxiliary"}
            }
            if keys:
                return keys
        except Exception:
            logger.info("strategy tracking metadata filter fell back to policy", exc_info=True)
        rows = self.db.execute(select(LowBuyResultSnapshot.strategy_key).distinct()).all()
        return {str(row[0]) for row in rows if participates_in_priority_board(str(row[0]))}

    def _recent_result_dates(self, range_days: int) -> list[str]:
        safe_days = max(1, min(range_days, 260))
        rows = (
            self.db.execute(
                select(LowBuyResultSnapshot.latest_trade_date)
                .distinct()
                .order_by(desc(LowBuyResultSnapshot.latest_trade_date))
                .limit(safe_days)
            )
            .scalars()
            .all()
        )
        return sorted(str(row) for row in rows)

    def _latest_bar_date(self) -> str:
        rows = DailyHistoryRepository(self.db).fetch_recent_trade_dates(1)
        return rows[-1] if rows else ""

    def _fetch_bars(self, groups: Iterable[TrackingGroup], *, latest_bar_date: str) -> dict[str, list[DailyBarRow]]:
        group_list = list(groups)
        if not group_list or not latest_bar_date:
            return {}
        symbols = sorted({item.symbol for item in group_list})
        start_date = calendar_lookback(min(self._first_signal_date(item) for item in group_list), 140)
        return DailyHistoryRepository(self.db).fetch_rows_for_symbols(symbols, start_date, latest_bar_date)

    def _fetch_light_bars(self, groups: Iterable[TrackingGroup], *, latest_bar_date: str) -> dict[str, list[DailyBarRow]]:
        group_list = list(groups)
        if not group_list or not latest_bar_date:
            return {}
        symbols = sorted({item.symbol for item in group_list})
        start_date = calendar_lookback(min(self._first_signal_date(item) for item in group_list), 140)
        return DailyHistoryRepository(self.db).fetch_light_rows_for_symbols(symbols, start_date, latest_bar_date)

    def _load_lifecycles(self, groups: Iterable[TrackingGroup]) -> dict[tuple[str, str, str], LowBuyTradeLifecycleSnapshot]:
        group_list = list(groups)
        if not group_list:
            return {}
        symbols = sorted({item.symbol for item in group_list})
        strategies = sorted({item.strategy_key for item in group_list})
        rows = (
            self.db.execute(
                select(LowBuyTradeLifecycleSnapshot)
                .where(
                    LowBuyTradeLifecycleSnapshot.symbol.in_(symbols),
                    LowBuyTradeLifecycleSnapshot.strategy_key.in_(strategies),
                )
                .order_by(LowBuyTradeLifecycleSnapshot.updated_at.desc())
            )
            .scalars()
            .all()
        )
        lifecycles: dict[tuple[str, str, str], LowBuyTradeLifecycleSnapshot] = {}
        for row in rows:
            key = (row.strategy_key, row.symbol, str(row.signal_trade_date))
            lifecycles.setdefault(key, row)
        return lifecycles

    def _build_summary_items(self, groups: list[TrackingGroup], *, latest_bar_date: str) -> list[StrategyTrackingItemOut]:
        preview = self._sort_groups(groups, sort="latest_desc")[:300]
        bars = self._fetch_light_bars(preview, latest_bar_date=latest_bar_date)
        lifecycles = self._load_lifecycles(preview)
        instruments = self._load_instrument_payloads(preview)
        return [
            self._build_item(group, bars.get(group.symbol, []), lifecycles.get(self._group_key(group)), latest_bar_date, instrument_payload=instruments.get(group.symbol))
            for group in preview
        ]

    def _load_read_model(
        self,
        *,
        range_days: int,
        strategy_key: str | None,
        strategy_family: str | None,
    ) -> tuple[list[StrategyTrackingItemOut], list[str]]:
        result_dates = self._recent_result_dates(range_days)
        if not result_dates:
            return [], []
        latest_bar_date = self._latest_bar_date()
        cache_key = (
            max(1, min(range_days, 260)),
            strategy_key or "",
            strategy_family or "",
            result_dates[0],
            result_dates[-1],
            latest_bar_date,
        )
        cached = _get_read_model_cache(cache_key)
        if cached is not None:
            return cached

        groups, partial_errors = self._load_groups_for_dates(result_dates=result_dates, strategy_key=strategy_key)
        if strategy_family:
            groups = [item for item in groups if get_strategy_tier(item.strategy_key).value == strategy_family]
        items = self._build_summary_items(groups, latest_bar_date=latest_bar_date)
        _set_read_model_cache(cache_key, (items, partial_errors))
        return items, partial_errors

    def _build_item(
        self,
        group: TrackingGroup,
        bars: list[DailyBarRow],
        lifecycle: LowBuyTradeLifecycleSnapshot | None,
        latest_bar_date: str,
        instrument_payload: dict[str, Any] | None = None,
    ) -> StrategyTrackingItemOut:
        first_date = self._first_signal_date(group)
        if instrument_payload:
            merged_payload = {**instrument_payload, **group.payload}
            group = TrackingGroup(
                strategy_key=group.strategy_key,
                symbol=group.symbol,
                rows=group.rows,
                latest_row=group.latest_row,
                first_row=group.first_row,
                payload=merged_payload,
                payload_error=group.payload_error,
            )
        return build_tracking_item(
            group=group,
            bars=bars,
            lifecycle=lifecycle,
            latest_bar_date=latest_bar_date,
            first_signal_date=first_date,
        )

    def _first_signal_date(self, group: TrackingGroup) -> str:
        payload_date = text(group.payload, "recommendation_start_date", "first_signal_date")
        return payload_date or str(group.first_row.latest_trade_date)

    def _group_key(self, group: TrackingGroup) -> tuple[str, str, str]:
        return group.strategy_key, group.symbol, self._first_signal_date(group)

    def _load_instrument_payloads(self, groups: list[TrackingGroup]) -> dict[str, dict[str, str]]:
        symbols = sorted({item.symbol for item in groups})
        if not symbols:
            return {}
        rows = self.db.execute(select(Instrument).where(Instrument.symbol.in_(symbols))).scalars().all()
        return {
            row.symbol: {"instrument_sector_name": row.sector_name or "", "instrument_market": row.market or "", "instrument_type": row.instrument_type or ""}
            for row in rows
        }

    def _sort_groups(self, groups: list[TrackingGroup], *, sort: str) -> list[TrackingGroup]:
        if sort == "latest_desc":
            return sorted(groups, key=lambda item: (item.latest_row.latest_trade_date, item.latest_row.score), reverse=True)
        return sorted(groups, key=lambda item: (item.latest_row.score, item.latest_row.latest_trade_date), reverse=True)

    def _range_start_date(self, range_days: int) -> str:
        dates = self._recent_result_dates(range_days)
        return dates[0] if dates else ""

    def _load_groups_for_dates(
        self,
        *,
        result_dates: list[str],
        strategy_key: str | None,
    ) -> tuple[list[TrackingGroup], list[str]]:
        if not result_dates:
            return [], []
        statement = select(LowBuyResultSnapshot).where(
            LowBuyResultSnapshot.latest_trade_date.in_(result_dates),
            LowBuyResultSnapshot.buy_signal_state.in_(TRACKED_SIGNAL_STATES),
        )
        if strategy_key:
            statement = statement.where(LowBuyResultSnapshot.strategy_key == strategy_key)
        rows = list(
            self.db.execute(
                statement.order_by(
                    LowBuyResultSnapshot.strategy_key.asc(),
                    LowBuyResultSnapshot.symbol.asc(),
                    LowBuyResultSnapshot.latest_trade_date.asc(),
                )
            )
            .scalars()
            .all()
        )
        return self._groups_from_rows(rows)

    def _groups_from_rows(self, rows: list[LowBuyResultSnapshot]) -> tuple[list[TrackingGroup], list[str]]:
        allowed = self._production_strategy_keys()
        grouped: dict[tuple[str, str], list[LowBuyResultSnapshot]] = defaultdict(list)
        for row in rows:
            if row.strategy_key not in allowed:
                continue
            grouped[(row.strategy_key, row.symbol)].append(row)
        groups: list[TrackingGroup] = []
        errors: list[str] = []
        for (_strategy, _symbol), group_rows in grouped.items():
            ordered = tuple(sorted(group_rows, key=lambda item: item.latest_trade_date))
            first_row = ordered[0]
            latest_row = ordered[-1]
            payload, payload_error = load_payload(latest_row)
            if payload_error:
                errors.append(f"{latest_row.strategy_key}/{latest_row.symbol}: {payload_error}")
            groups.append(
                TrackingGroup(
                    strategy_key=latest_row.strategy_key,
                    symbol=latest_row.symbol,
                    rows=ordered,
                    latest_row=latest_row,
                    first_row=first_row,
                    payload=payload,
                    payload_error=payload_error,
                )
            )
        return self._sort_groups(groups, sort="latest_desc"), errors
