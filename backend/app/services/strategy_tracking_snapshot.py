from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.timezone import beijing_now
from app.models.entities import StrategyTrackingSnapshot
from app.models.schema_defs.strategy_tracking import (
    StrategyTrackingHoldingAnalysisResponse,
    StrategyTrackingItemOut,
    StrategyTrackingListResponse,
    StrategyTrackingSnapshotAuditOut,
    StrategyTrackingSnapshotPayloadOut,
    StrategyTrackingSnapshotRebuildResponse,
    StrategyTrackingSnapshotResponse,
)
from app.services.strategy_tracking import DEFAULT_LIMIT, DEFAULT_RANGE_DAYS, MAX_LIMIT, StrategyTrackingService
from app.services.strategy_tracking_filters import filter_items, sort_items
from app.services.strategy_tracking_helpers import build_performance, build_market_segments, build_summary
from app.services.strategy_tracking_usability import build_holding_analysis

logger = logging.getLogger(__name__)

SNAPSHOT_STALE_AFTER = timedelta(minutes=90)
DEFAULT_MARKET_SCOPE = "all"


class StrategyTrackingSnapshotBuilder:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_snapshot(
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
    ) -> StrategyTrackingSnapshotResponse:
        row = self._latest_snapshot(
            range_days=range_days,
            strategy_key=strategy_key,
            strategy_family=strategy_family,
            market_scope=DEFAULT_MARKET_SCOPE,
        )
        if row is None:
            safe_limit = max(1, min(limit, MAX_LIMIT))
            return StrategyTrackingSnapshotResponse(
                status="missing",
                stale=True,
                limit=safe_limit,
                offset=max(0, offset),
                sort=sort,
                partial_errors=["strategy_tracking_snapshot_missing"],
                notes=["策略跟踪快照尚未生成，管理员可执行 /strategy-tracking/snapshot/rebuild。"],
            )

        payload = _payload_from_row(row)
        all_items = list(payload.items)
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
        sorted_items = sort_items(items, sort=sort)
        safe_limit = max(1, min(limit, MAX_LIMIT))
        safe_offset = max(0, offset)
        page_items = sorted_items[safe_offset : safe_offset + safe_limit]
        summary = build_summary(items)
        summary.shadow_observation_count = sum(item.observation_count for item in payload.shadow_observations)
        filtered_payload = StrategyTrackingSnapshotPayloadOut(
            summary=summary,
            items=page_items,
            performance=build_performance(items),
            market_segments=build_market_segments(items),
            holding_summary=StrategyTrackingHoldingAnalysisResponse(
                items=build_holding_analysis(items),
                generated_at=summary.generated_at,
                data_quality=summary.data_quality,
                production_writeable=False,
            ),
            shadow_observations=payload.shadow_observations,
            audit=payload.audit,
        )
        stale = _row_is_stale(row)
        status = "stale" if stale and row.status == "fresh" else row.status
        return StrategyTrackingSnapshotResponse(
            status=status,
            stale=stale,
            generated_at=_datetime_string(row.generated_at),
            source_data_cutoff=row.source_data_cutoff,
            data_version=row.data_version,
            snapshot_key=row.snapshot_key,
            as_of_date=row.as_of_date,
            payload=filtered_payload,
            total=len(items),
            limit=safe_limit,
            offset=safe_offset,
            sort=sort,
            partial_errors=_snapshot_partial_errors(row, stale),
            notes=[
                "首页读取策略跟踪快照，不在用户请求时重算策略表现。",
                "后验表现仅使用首次推荐日之后的行情，不回写策略分数或交易账本。",
            ],
        )

    def rebuild_snapshot(
        self,
        *,
        range_days: int = DEFAULT_RANGE_DAYS,
        strategy_key: str | None = None,
        strategy_family: str | None = None,
    ) -> StrategyTrackingSnapshotRebuildResponse:
        started = time.monotonic()
        normalized_range = _safe_range(range_days)
        snapshot_key = build_snapshot_key(
            range_days=normalized_range,
            strategy_key=strategy_key,
            strategy_family=strategy_family,
            market_scope=DEFAULT_MARKET_SCOPE,
        )
        stale_snapshot = self._latest_snapshot(
            range_days=normalized_range,
            strategy_key=strategy_key,
            strategy_family=strategy_family,
            market_scope=DEFAULT_MARKET_SCOPE,
        )
        try:
            service = StrategyTrackingService(self.db)
            items, partial_errors = service._load_read_model(  # noqa: SLF001 - snapshot builder is the durable read-model adapter.
                range_days=normalized_range,
                strategy_key=strategy_key,
                strategy_family=strategy_family,
            )
            shadow = service.shadow_observations(range_days=normalized_range, strategy_key=strategy_key, items=items)
            summary = build_summary(items)
            summary.shadow_observation_count = sum(item.observation_count for item in shadow)
            result = StrategyTrackingListResponse(
                items=items,
                total=len(items),
                limit=len(items),
                offset=0,
                summary=summary,
                performance=build_performance(items),
                market_segments=build_market_segments(items),
                shadow_observations=shadow,
                partial_errors=partial_errors,
            )
            payload, audit = _snapshot_payload_from_result(result)
            if audit.violation_count > 0:
                raise ValueError(f"策略跟踪快照防未来函数校验失败: {audit.audit_flags[:3]}")
            generated_at = beijing_now().replace(tzinfo=None)
            source_data_cutoff = _source_data_cutoff(payload.items)
            data_version = _data_version(
                as_of_date=_as_of_date(payload.items),
                source_data_cutoff=source_data_cutoff,
                item_count=len(payload.items),
            )
            metrics = {
                "elapsed_ms": int((time.monotonic() - started) * 1000),
                "item_count": len(payload.items),
                "partial_error_count": len(result.partial_errors),
                "audit": audit.model_dump(mode="json"),
                "source": "strategy_tracking_read_model",
            }
            row = self.db.execute(
                select(StrategyTrackingSnapshot).where(StrategyTrackingSnapshot.snapshot_key == snapshot_key)
            ).scalar_one_or_none()
            if row is None:
                row = StrategyTrackingSnapshot(snapshot_key=snapshot_key)
                self.db.add(row)
            row.as_of_date = _as_of_date(payload.items)
            row.range_days = normalized_range
            row.strategy_key = strategy_key or ""
            row.strategy_family = strategy_family or ""
            row.market_scope = DEFAULT_MARKET_SCOPE
            row.filter_hash = _filter_hash({"range": normalized_range, "strategy_key": strategy_key or "", "strategy_family": strategy_family or ""})
            row.data_version = data_version
            row.status = "fresh"
            row.generated_at = generated_at
            row.source_data_cutoff = source_data_cutoff
            row.payload_json = payload.model_dump_json()
            row.metrics_json = json.dumps(metrics, ensure_ascii=False, default=str)
            row.error_message = ""
            self.db.commit()
            return StrategyTrackingSnapshotRebuildResponse(
                ok=True,
                status="fresh",
                snapshot_key=snapshot_key,
                generated_at=_datetime_string(generated_at),
                source_data_cutoff=source_data_cutoff,
                data_version=data_version,
                item_count=len(payload.items),
                elapsed_ms=metrics["elapsed_ms"],
                stale_snapshot_used=False,
            )
        except Exception as exc:
            self.db.rollback()
            logger.exception("strategy tracking snapshot rebuild failed")
            self._record_failed_snapshot(
                snapshot_key=snapshot_key,
                range_days=normalized_range,
                strategy_key=strategy_key,
                strategy_family=strategy_family,
                error_message=str(exc),
            )
            return StrategyTrackingSnapshotRebuildResponse(
                ok=False,
                status="failed",
                snapshot_key=snapshot_key,
                elapsed_ms=int((time.monotonic() - started) * 1000),
                stale_snapshot_used=stale_snapshot is not None,
                error_message=str(exc),
            )

    def _latest_snapshot(
        self,
        *,
        range_days: int,
        strategy_key: str | None,
        strategy_family: str | None,
        market_scope: str,
    ) -> StrategyTrackingSnapshot | None:
        snapshot_key = build_snapshot_key(
            range_days=_safe_range(range_days),
            strategy_key=strategy_key,
            strategy_family=strategy_family,
            market_scope=market_scope,
        )
        row = self.db.execute(
            select(StrategyTrackingSnapshot)
            .where(StrategyTrackingSnapshot.snapshot_key == snapshot_key)
            .where(StrategyTrackingSnapshot.status.in_(("fresh", "stale")))
            .order_by(desc(StrategyTrackingSnapshot.generated_at), desc(StrategyTrackingSnapshot.id))
            .limit(1)
        ).scalar_one_or_none()
        if row is not None:
            return row
        return self.db.execute(
            select(StrategyTrackingSnapshot)
            .where(StrategyTrackingSnapshot.range_days == _safe_range(range_days))
            .where(StrategyTrackingSnapshot.strategy_key == (strategy_key or ""))
            .where(StrategyTrackingSnapshot.strategy_family == (strategy_family or ""))
            .where(StrategyTrackingSnapshot.market_scope == market_scope)
            .where(StrategyTrackingSnapshot.status.in_(("fresh", "stale")))
            .order_by(desc(StrategyTrackingSnapshot.generated_at), desc(StrategyTrackingSnapshot.id))
            .limit(1)
        ).scalar_one_or_none()

    def _record_failed_snapshot(
        self,
        *,
        snapshot_key: str,
        range_days: int,
        strategy_key: str | None,
        strategy_family: str | None,
        error_message: str,
    ) -> None:
        try:
            row = self.db.execute(
                select(StrategyTrackingSnapshot).where(StrategyTrackingSnapshot.snapshot_key == snapshot_key)
            ).scalar_one_or_none()
            if row is None:
                row = StrategyTrackingSnapshot(snapshot_key=snapshot_key)
                self.db.add(row)
                row.payload_json = StrategyTrackingSnapshotPayloadOut().model_dump_json()
                row.metrics_json = "{}"
                row.status = "failed"
            elif row.status in {"fresh", "stale"}:
                row.error_message = error_message[:1000]
                self.db.commit()
                return
            row.range_days = range_days
            row.strategy_key = strategy_key or ""
            row.strategy_family = strategy_family or ""
            row.market_scope = DEFAULT_MARKET_SCOPE
            row.filter_hash = _filter_hash({"range": range_days, "strategy_key": strategy_key or "", "strategy_family": strategy_family or ""})
            row.status = "failed"
            row.error_message = error_message[:1000]
            self.db.commit()
        except Exception:
            self.db.rollback()
            logger.exception("failed to persist strategy tracking snapshot failure")


def build_snapshot_key(
    *,
    range_days: int,
    strategy_key: str | None,
    strategy_family: str | None,
    market_scope: str = DEFAULT_MARKET_SCOPE,
) -> str:
    return "strategy-tracking:" + hashlib.sha256(
        json.dumps(
            {
                "range": _safe_range(range_days),
                "strategy_key": strategy_key or "",
                "strategy_family": strategy_family or "",
                "market_scope": market_scope,
            },
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def _snapshot_payload_from_result(result: StrategyTrackingListResponse) -> tuple[StrategyTrackingSnapshotPayloadOut, StrategyTrackingSnapshotAuditOut]:
    all_items = list(result.items)
    audit = _audit_items(all_items)
    payload = StrategyTrackingSnapshotPayloadOut(
        summary=result.summary,
        items=all_items,
        performance=result.performance,
        market_segments=result.market_segments,
        holding_summary=StrategyTrackingHoldingAnalysisResponse(
            items=build_holding_analysis(all_items),
            generated_at=result.summary.generated_at,
            data_quality=result.summary.data_quality,
            production_writeable=False,
        ),
        shadow_observations=result.shadow_observations,
        audit=audit,
    )
    return payload, audit


def _audit_items(items: list[StrategyTrackingItemOut]) -> StrategyTrackingSnapshotAuditOut:
    flags: list[str] = []
    for item in items:
        signal_generated_at = item.signal_generated_at or item.first_signal_date
        data_cutoff_at = item.data_cutoff_at or item.first_signal_date
        if _compare_temporal(data_cutoff_at, signal_generated_at) > 0:
            flags.append(f"{item.id}:data_cutoff_after_signal")
        if item.posterior_start_date and _compare_dates(item.posterior_start_date, item.first_signal_date) <= 0:
            flags.append(f"{item.id}:posterior_not_after_signal")
        if item.lookback_end_date and _compare_dates(item.lookback_end_date, item.first_signal_date) > 0:
            flags.append(f"{item.id}:lookback_after_signal")
    return StrategyTrackingSnapshotAuditOut(
        future_leak_check="needs_review" if flags else "passed",
        checked_count=len(items),
        violation_count=len(flags),
        abnormal_return_count=sum(1 for item in items if item.abnormal_return),
        needs_review_count=sum(1 for item in items if item.needs_review),
        audit_flags=flags[:100],
    )


def _payload_from_row(row: StrategyTrackingSnapshot) -> StrategyTrackingSnapshotPayloadOut:
    try:
        return StrategyTrackingSnapshotPayloadOut.model_validate_json(row.payload_json or "{}")
    except Exception:
        logger.warning("strategy tracking snapshot payload schema mismatch id=%s", row.id, exc_info=True)
        return StrategyTrackingSnapshotPayloadOut()


def _safe_range(range_days: int) -> int:
    return max(1, min(int(range_days or DEFAULT_RANGE_DAYS), 260))


def _as_of_date(items: list[StrategyTrackingItemOut]) -> str:
    return max((item.latest_trade_date or item.latest_signal_date for item in items), default="")


def _source_data_cutoff(items: list[StrategyTrackingItemOut]) -> str:
    cutoffs = [item.data_cutoff_at or item.lookback_end_date or item.first_signal_date for item in items]
    return max((item for item in cutoffs if item), default="")


def _data_version(*, as_of_date: str, source_data_cutoff: str, item_count: int) -> str:
    return f"{as_of_date or 'unknown'}:{source_data_cutoff or 'unknown'}:{item_count}"


def _filter_hash(payload: dict[str, object]) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _row_is_stale(row: StrategyTrackingSnapshot) -> bool:
    generated_at = row.generated_at
    if generated_at is None:
        return True
    now = beijing_now().replace(tzinfo=None)
    return now - generated_at > SNAPSHOT_STALE_AFTER


def _snapshot_partial_errors(row: StrategyTrackingSnapshot, stale: bool) -> list[str]:
    errors: list[str] = []
    if stale:
        errors.append("strategy_tracking_snapshot_stale")
    if row.error_message:
        errors.append(row.error_message)
    return errors


def _datetime_string(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.isoformat(sep=" ", timespec="seconds")


def _compare_temporal(left: str, right: str) -> int:
    if len(left or "") < 11 or len(right or "") < 11:
        return _compare_dates(left, right)
    return _compare_keys(_temporal_key(left), _temporal_key(right))


def _compare_dates(left: str, right: str) -> int:
    return _compare_keys((left or "")[:10], (right or "")[:10])


def _temporal_key(value: str) -> str:
    return (value or "").replace("T", " ")[:19]


def _compare_keys(left: str, right: str) -> int:
    if not left or not right:
        return 0
    if left > right:
        return 1
    if left < right:
        return -1
    return 0
