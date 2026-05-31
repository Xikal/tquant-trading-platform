from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.entities import ProductionSignalLedger, StrategyDriftSnapshot
from app.services.track_record.schemas import (
    TrackRecordDriftItemOut,
    TrackRecordDriftResponse,
    TrackRecordLedgerItemOut,
    TrackRecordLedgerResponse,
)

router = APIRouter(prefix="/track-record", dependencies=[Depends(get_current_user)])


@router.get("/drift", response_model=TrackRecordDriftResponse)
def track_record_drift_view(
    strategy_key: str | None = Query(None, max_length=80),
    window_days: int | None = Query(None, ge=1, le=520),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> TrackRecordDriftResponse:
    statement = select(StrategyDriftSnapshot)
    count_statement = select(func.count(StrategyDriftSnapshot.id))
    if strategy_key:
        statement = statement.where(StrategyDriftSnapshot.strategy_key == strategy_key)
        count_statement = count_statement.where(StrategyDriftSnapshot.strategy_key == strategy_key)
    if window_days:
        statement = statement.where(StrategyDriftSnapshot.window_days == window_days)
        count_statement = count_statement.where(StrategyDriftSnapshot.window_days == window_days)
    rows = db.execute(
        statement.order_by(
            StrategyDriftSnapshot.as_of_date.desc(),
            StrategyDriftSnapshot.strategy_key.asc(),
            StrategyDriftSnapshot.window_days.asc(),
        ).limit(limit)
    ).scalars().all()
    total = int(db.execute(count_statement).scalar() or 0)
    return TrackRecordDriftResponse(items=[_drift_out(row) for row in rows], total=total)


@router.get("/ledger", response_model=TrackRecordLedgerResponse)
def track_record_ledger_view(
    strategy_key: str | None = Query(None, max_length=80),
    symbol: str | None = Query(None, max_length=16),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> TrackRecordLedgerResponse:
    statement = select(ProductionSignalLedger)
    count_statement = select(func.count(ProductionSignalLedger.id))
    if strategy_key:
        statement = statement.where(ProductionSignalLedger.strategy_key == strategy_key)
        count_statement = count_statement.where(ProductionSignalLedger.strategy_key == strategy_key)
    if symbol:
        statement = statement.where(ProductionSignalLedger.symbol == symbol)
        count_statement = count_statement.where(ProductionSignalLedger.symbol == symbol)
    rows = db.execute(
        statement.order_by(ProductionSignalLedger.signal_date.desc(), ProductionSignalLedger.id.desc())
        .offset(offset)
        .limit(limit)
    ).scalars().all()
    total = int(db.execute(count_statement).scalar() or 0)
    return TrackRecordLedgerResponse(
        items=[_ledger_out(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


def _drift_out(row: StrategyDriftSnapshot) -> TrackRecordDriftItemOut:
    return TrackRecordDriftItemOut(
        strategy_key=row.strategy_key,
        as_of_date=row.as_of_date,
        window_days=int(row.window_days or 0),
        realized_pf=float(row.realized_pf) if row.realized_pf is not None else None,
        expected_pf=float(row.expected_pf) if row.expected_pf is not None else None,
        realized_avg=float(row.realized_avg or 0.0),
        expected_avg=float(row.expected_avg or 0.0),
        realized_winrate=float(row.realized_winrate or 0.0),
        expected_winrate=float(row.expected_winrate or 0.0),
        realized_max5=float(row.realized_max5 or 0.0),
        backtest_max5=float(row.backtest_max5 or 0.0),
        realized_max10=float(row.realized_max10 or 0.0),
        backtest_max10=float(row.backtest_max10 or 0.0),
        tracking_error=float(row.tracking_error or 0.0),
        decay_pct=float(row.decay_pct or 0.0),
        drift_flag=row.drift_flag or "insufficient_sample",
        sample_settled=int(row.sample_settled or 0),
        created_at=row.created_at,
    )


def _ledger_out(row: ProductionSignalLedger) -> TrackRecordLedgerItemOut:
    return TrackRecordLedgerItemOut(
        id=int(row.id),
        signal_date=row.signal_date,
        strategy_key=row.strategy_key,
        symbol=row.symbol,
        name=row.name or "",
        signal_state=row.signal_state,
        production_score=float(row.production_score) if row.production_score is not None else None,
        priority_score=float(row.priority_score or 0.0),
        data_quality=row.data_quality or "unknown",
        signal_time=row.signal_time,
        data_cutoff_time=row.data_cutoff_time,
        return_start_time=row.return_start_time,
        source_version=row.source_version or "",
    )
