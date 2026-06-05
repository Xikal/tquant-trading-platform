from __future__ import annotations

from datetime import date, datetime
from time import perf_counter
from typing import Any

from sqlalchemy.orm import Session

from app.services.trading_experience import relative_strength, review_pool, trade_journal
from app.services.trading_experience.config import ENGINE_VERSION
from app.services.trading_experience.schemas import (
    BoardFilter,
    DataQuality,
    ReviewWorkspaceItem,
    ReviewWorkspaceReminder,
    ReviewWorkspaceResponse,
    ReviewWorkspaceSourceStatus,
    ReviewWorkspaceSummary,
)


def build_workspace(
    db: Session,
    *,
    pool_date: date | None,
    limit: int,
    board_filter: BoardFilter,
    relative_strength_enabled: bool,
    user_id: int | None,
) -> ReviewWorkspaceResponse:
    started = perf_counter()
    sources: list[ReviewWorkspaceSourceStatus] = []

    source_started = perf_counter()
    pool_items = review_pool.list_review_pool(db, pool_date=pool_date, limit=limit, board_filter=board_filter)
    sources.append(
        ReviewWorkspaceSourceStatus(
            source="review_pool",
            status="ok" if pool_items else "insufficient",
            elapsed_ms=_elapsed_ms(source_started),
            item_count=len(pool_items),
            reason="" if pool_items else "empty_review_pool",
        )
    )

    source_started = perf_counter()
    journal_entries = trade_journal.list_entries(
        db,
        user_id=user_id,
        account_id=None,
        symbol=None,
        limit=max(limit * 4, 80),
    )
    sources.append(
        ReviewWorkspaceSourceStatus(
            source="trade_journal",
            status="ok",
            elapsed_ms=_elapsed_ms(source_started),
            item_count=len(journal_entries),
        )
    )
    journal_by_symbol: dict[str, list] = {}
    for entry in journal_entries:
        journal_by_symbol.setdefault(entry.symbol, []).append(entry)

    source_started = perf_counter()
    rs_items = (
        relative_strength.build_board(db, trade_date=pool_date, limit=max(limit * 4, 80))
        if relative_strength_enabled
        else []
    )
    sources.append(
        ReviewWorkspaceSourceStatus(
            source="relative_strength",
            status=("ok" if rs_items else "insufficient") if relative_strength_enabled else "disabled",
            elapsed_ms=_elapsed_ms(source_started),
            item_count=len(rs_items),
            reason="" if relative_strength_enabled else "feature_flag_disabled",
        )
    )
    rs_by_symbol = {item.symbol: item for item in rs_items}

    workspace_items: list[ReviewWorkspaceItem] = []
    for pool_item in pool_items:
        entries = journal_by_symbol.get(pool_item.symbol, [])
        status = _review_status(pool_item.data_quality, pool_item.status, bool(entries))
        workspace_items.append(
            ReviewWorkspaceItem(
                review_key=f"{pool_item.pool_date}:{pool_item.symbol}",
                pool_item=pool_item,
                journal_entries=entries,
                relative_strength=rs_by_symbol.get(pool_item.symbol),
                review_status=status,
                next_action_label=_next_action_label(status),
            )
        )

    summary = ReviewWorkspaceSummary(
        pending_review_count=sum(1 for item in workspace_items if item.review_status == "pending"),
        retained_count=sum(1 for item in workspace_items if item.pool_item.status == "retained"),
        dropped_count=sum(1 for item in workspace_items if item.pool_item.status == "dropped"),
        missing_journal_count=sum(1 for item in workspace_items if not item.journal_entries),
        journal_count=sum(len(item.journal_entries) for item in workspace_items),
        relative_strength_count=sum(1 for item in workspace_items if item.relative_strength is not None),
        completion_rate_pct=_completion_rate(workspace_items),
        seven_day_discipline_pass_rate_pct=_discipline_pass_rate(journal_entries),
        seven_day_journal_count=len(journal_entries),
        market_context=_market_context(rs_items),
    )

    return ReviewWorkspaceResponse(
        enabled=True,
        review_enabled=True,
        relative_strength_enabled=relative_strength_enabled,
        pool_date=pool_items[0].pool_date if pool_items else (pool_date.isoformat() if pool_date else None),
        board_filter=board_filter,
        reminder=_reminder(pool_items, workspace_items, pool_date),
        summary=summary,
        sources=sources,
        cache_status="fresh" if pool_items else "miss",
        elapsed_ms=_elapsed_ms(started),
        items=workspace_items,
        total=len(workspace_items),
        data_quality="ok" if workspace_items else "insufficient",
        as_of=datetime.now(),
        engine_version=ENGINE_VERSION,
        source="review_workspace",
        research_only=True,
    )


def disabled_workspace(
    *,
    review_enabled: bool,
    relative_strength_enabled: bool,
    board_filter: BoardFilter,
) -> ReviewWorkspaceResponse:
    return ReviewWorkspaceResponse(
        enabled=False,
        review_enabled=review_enabled,
        relative_strength_enabled=relative_strength_enabled,
        board_filter=board_filter,
        reminder=ReviewWorkspaceReminder(
            status="blocked",
            message="复盘中心未开启",
            refresh_queued=False,
            data_quality="blocked",
        ),
        data_quality="blocked",
        as_of=datetime.now(),
        engine_version=ENGINE_VERSION,
        source="feature_flag",
        research_only=True,
    )


def _review_status(data_quality: DataQuality, pool_status: str, has_journal: bool) -> str:
    if data_quality != "ok":
        return "data_issue"
    if has_journal:
        return "journaled"
    if pool_status == "retained":
        return "retained"
    if pool_status == "dropped":
        return "dropped"
    return "pending"


def _next_action_label(status: str) -> str:
    if status == "journaled":
        return "查看纪律"
    if status == "dropped":
        return "查看剔除原因"
    if status == "data_issue":
        return "检查数据"
    return "写复盘"


def _market_context(items: list[Any]) -> str:
    if not items:
        return "no_relative_strength"
    index_pcts = [float(item.index_pct or 0.0) for item in items]
    avg_index = sum(index_pcts) / len(index_pcts)
    if avg_index <= -1.0:
        return "market_down_day"
    return "normal_day"


def _elapsed_ms(started: float) -> float:
    return round((perf_counter() - started) * 1000.0, 3)


def _completion_rate(items: list[ReviewWorkspaceItem]) -> float:
    if not items:
        return 0.0
    completed = sum(1 for item in items if item.journal_entries)
    return round(completed * 100.0 / len(items), 2)


def _discipline_pass_rate(entries: list[Any]) -> float | None:
    checked = []
    for entry in entries:
        flags = entry.discipline_flags or {}
        if flags:
            checked.append(all(bool(value) for value in flags.values()))
    if not checked:
        return None
    return round(sum(1 for value in checked if value) * 100.0 / len(checked), 2)


def _reminder(
    pool_items: list[Any],
    workspace_items: list[ReviewWorkspaceItem],
    pool_date: date | None,
) -> ReviewWorkspaceReminder:
    if not pool_items:
        return ReviewWorkspaceReminder(
            status="insufficient",
            message="复盘池暂无可用数据",
            pool_date=pool_date.isoformat() if pool_date else None,
            refresh_queued=False,
            data_quality="insufficient",
        )
    missing = sum(1 for item in workspace_items if not item.journal_entries)
    return ReviewWorkspaceReminder(
        status="ready",
        message=f"今日复盘池已生成，待补纪律日志 {missing} 条",
        pool_date=pool_items[0].pool_date,
        refresh_queued=False,
        last_success_at=datetime.now(),
        data_quality="ok",
    )
