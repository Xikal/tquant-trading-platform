from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Iterable

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.entities import LowBuyResultSnapshot, LowBuyTradeLifecycleSnapshot
from app.models.schema_defs.strategy_tracking import (
    StrategyTrackingDetailResponse,
    StrategyTrackingItemOut,
    StrategyTrackingListResponse,
    StrategyTrackingPerformanceOut,
    StrategyTrackingRefreshResponse,
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
from app.services.strategy_tracking_helpers import (
    build_performance,
    build_summary,
    compact_payload,
    load_payload,
    parse_item_id,
    text,
)

logger = logging.getLogger(__name__)


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
        sort: str = "max_gain_desc",
        limit: int = DEFAULT_LIMIT,
        offset: int = 0,
    ) -> StrategyTrackingListResponse:
        safe_limit = max(1, min(limit, MAX_LIMIT))
        safe_offset = max(0, offset)
        groups, partial_errors = self._load_groups(range_days=range_days, strategy_key=strategy_key)
        if strategy_family:
            groups = [item for item in groups if get_strategy_tier(item.strategy_key).value == strategy_family]
        if signal_state:
            groups = [item for item in groups if item.latest_row.buy_signal_state == signal_state]
        latest_bar_date = self._latest_bar_date()
        all_items = self._build_summary_items(groups, latest_bar_date=latest_bar_date)
        items = self._filter_items(
            all_items,
            lifecycle_status=lifecycle_status,
            data_quality=data_quality,
            hit_entry=hit_entry,
            stopped=stopped,
        )
        items = self._sort_items(items, sort=sort)
        total = len(items)
        items = items[safe_offset : safe_offset + safe_limit]
        summary = build_summary(all_items)
        performance = build_performance(all_items)
        return StrategyTrackingListResponse(
            items=items,
            total=total,
            limit=safe_limit,
            offset=safe_offset,
            sort=sort,
            summary=summary,
            performance=performance,
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
        item = self._build_item(group, bars, lifecycle, latest_bar_date)
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
        if not dates:
            return [], []
        statement = select(LowBuyResultSnapshot).where(
            LowBuyResultSnapshot.latest_trade_date.in_(dates),
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
        start_date = min(self._first_signal_date(item) for item in group_list)
        return DailyHistoryRepository(self.db).fetch_rows_for_symbols(symbols, start_date, latest_bar_date)

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
        bars = self._fetch_bars(preview, latest_bar_date=latest_bar_date)
        lifecycles = self._load_lifecycles(preview)
        return [self._build_item(group, bars.get(group.symbol, []), lifecycles.get(self._group_key(group)), latest_bar_date) for group in preview]

    def _build_item(
        self,
        group: TrackingGroup,
        bars: list[DailyBarRow],
        lifecycle: LowBuyTradeLifecycleSnapshot | None,
        latest_bar_date: str,
    ) -> StrategyTrackingItemOut:
        first_date = self._first_signal_date(group)
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

    def _filter_items(
        self,
        items: list[StrategyTrackingItemOut],
        *,
        lifecycle_status: str | None,
        data_quality: str | None,
        hit_entry: bool | None,
        stopped: bool | None,
    ) -> list[StrategyTrackingItemOut]:
        result = items
        if lifecycle_status:
            result = [item for item in result if item.lifecycle_status == lifecycle_status]
        if data_quality:
            result = [item for item in result if item.data_quality == data_quality]
        if hit_entry is not None:
            result = [item for item in result if item.entry_touched == hit_entry]
        if stopped is not None:
            result = [item for item in result if item.stop_triggered == stopped]
        return result

    def _sort_groups(self, groups: list[TrackingGroup], *, sort: str) -> list[TrackingGroup]:
        if sort == "latest_desc":
            return sorted(groups, key=lambda item: (item.latest_row.latest_trade_date, item.latest_row.score), reverse=True)
        return sorted(groups, key=lambda item: (item.latest_row.score, item.latest_row.latest_trade_date), reverse=True)

    def _sort_items(self, items: list[StrategyTrackingItemOut], *, sort: str) -> list[StrategyTrackingItemOut]:
        if sort == "current_return_desc":
            return sorted(items, key=lambda item: item.current_return_pct or -999.0, reverse=True)
        if sort == "drawdown_asc":
            return sorted(items, key=lambda item: item.max_drawdown_pct or 0.0)
        if sort == "days_desc":
            return sorted(items, key=lambda item: item.recommendation_days, reverse=True)
        if sort == "risk_desc":
            return sorted(items, key=lambda item: (item.stop_triggered, -(item.max_drawdown_pct or 0.0)), reverse=True)
        return sorted(items, key=lambda item: item.max_gain_pct or -999.0, reverse=True)
