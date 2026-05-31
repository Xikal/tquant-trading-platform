from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import DailyBarSnapshot, ProductionSignalLedger, SignalRealizedOutcome
from scripts.low_buy_market_backtest_reporting import TradeOutcome, portfolio_backtest_metrics


DEFAULT_HORIZONS = (1, 3, 5, 10)


def refresh_realized_outcomes(
    db: Session,
    *,
    as_of: date,
    horizons: list[int] | tuple[int, ...] = DEFAULT_HORIZONS,
) -> dict[str, Any]:
    if not get_settings().track_record_enabled:
        return {"ok": True, "settled": 0, "unsettled": 0, "disabled": True}
    ledgers = db.execute(select(ProductionSignalLedger).order_by(ProductionSignalLedger.id.asc())).scalars().all()
    settled = 0
    unsettled = 0
    for ledger in ledgers:
        bars = _future_bars(db, ledger=ledger, as_of=as_of)
        for horizon in horizons:
            if _outcome_exists(db, ledger_id=int(ledger.id), horizon_days=int(horizon)):
                continue
            outcome = _compute_horizon_outcome(ledger, bars, int(horizon))
            db.add(outcome)
            if outcome.settled:
                settled += 1
            else:
                unsettled += 1
    db.flush()
    return {"ok": True, "settled": settled, "unsettled": unsettled}


def compute_portfolio_realized_metrics(
    db: Session,
    *,
    max_positions: int = 5,
    horizon_days: int = 5,
    paper_account_id: int | None = None,
) -> dict[str, Any]:
    if paper_account_id:
        from app.services.paper.performance import PaperPerformanceService

        return PaperPerformanceService(db).compute_portfolio_execution_preview(paper_account_id)
    outcomes = _ledger_trade_outcomes(db, horizon_days=horizon_days)
    return portfolio_backtest_metrics(
        outcomes,
        states={"buy_now", "soft_buy_now"},
        max_positions=max_positions,
        sort_by_production_score=True,
    )


def _compute_horizon_outcome(
    ledger: ProductionSignalLedger,
    bars: list[DailyBarSnapshot],
    horizon_days: int,
) -> SignalRealizedOutcome:
    if len(bars) < horizon_days:
        return SignalRealizedOutcome(
            ledger_id=ledger.id,
            horizon_days=horizon_days,
            return_pct=None,
            max_gain_pct=None,
            max_drawdown_pct=None,
            exit_reason=f"missing_horizon_{horizon_days}d",
            return_start_time=ledger.return_start_time,
            settled=False,
            data_quality="missing",
        )
    entry_bar = bars[0]
    exit_bar = bars[horizon_days - 1]
    entry_price = float(entry_bar.close_price or 0.0)
    if entry_price <= 0:
        return SignalRealizedOutcome(
            ledger_id=ledger.id,
            horizon_days=horizon_days,
            return_pct=None,
            max_gain_pct=None,
            max_drawdown_pct=None,
            exit_reason="invalid_entry_price",
            return_start_time=ledger.return_start_time,
            settled=False,
            data_quality="invalid_price",
        )
    scoped = bars[:horizon_days]
    return_pct = _pct(float(exit_bar.close_price or 0.0), entry_price)
    max_gain = max(_pct(float(bar.high_price or 0.0), entry_price) for bar in scoped)
    max_drawdown = min(_pct(float(bar.low_price or 0.0), entry_price) for bar in scoped)
    return SignalRealizedOutcome(
        ledger_id=ledger.id,
        horizon_days=horizon_days,
        return_pct=return_pct,
        max_gain_pct=max_gain,
        max_drawdown_pct=max_drawdown,
        exit_reason=f"horizon_{horizon_days}d",
        return_start_time=ledger.return_start_time,
        settled=True,
        data_quality="ok",
    )


def _future_bars(db: Session, *, ledger: ProductionSignalLedger, as_of: date) -> list[DailyBarSnapshot]:
    start_date = ledger.return_start_time.date()
    return (
        db.execute(
            select(DailyBarSnapshot)
            .where(DailyBarSnapshot.symbol == ledger.symbol)
            .where(DailyBarSnapshot.trade_date >= start_date)
            .where(DailyBarSnapshot.trade_date <= as_of)
            .order_by(DailyBarSnapshot.trade_date.asc())
        )
        .scalars()
        .all()
    )


def _outcome_exists(db: Session, *, ledger_id: int, horizon_days: int) -> bool:
    return (
        db.execute(
            select(SignalRealizedOutcome.id)
            .where(SignalRealizedOutcome.ledger_id == ledger_id)
            .where(SignalRealizedOutcome.horizon_days == horizon_days)
            .limit(1)
        ).scalar_one_or_none()
        is not None
    )


def _ledger_trade_outcomes(db: Session, *, horizon_days: int) -> list[TradeOutcome]:
    rows = (
        db.execute(
            select(ProductionSignalLedger, SignalRealizedOutcome)
            .join(SignalRealizedOutcome, SignalRealizedOutcome.ledger_id == ProductionSignalLedger.id)
            .where(SignalRealizedOutcome.horizon_days == horizon_days)
            .where(SignalRealizedOutcome.settled.is_(True))
            .order_by(ProductionSignalLedger.signal_date.asc(), ProductionSignalLedger.id.asc())
        )
        .all()
    )
    outcomes: list[TradeOutcome] = []
    for ledger, outcome in rows:
        return_pct = float(outcome.return_pct or 0.0)
        outcomes.append(
            TradeOutcome(
                symbol=str(ledger.symbol or ""),
                name=str(ledger.name or ledger.symbol or ""),
                signal_date=ledger.signal_date.isoformat() if ledger.signal_date else "",
                strategy_key=str(ledger.strategy_key or ""),
                buy_signal_state=str(ledger.signal_state or ""),
                entry_price=float(ledger.entry_zone_low or ledger.entry_zone_high or 0.0),
                execution_status="filled",
                net_return_pct=return_pct,
                execution_exit_reason=str(outcome.exit_reason or f"horizon_{horizon_days}d"),
                return_1d=return_pct if horizon_days == 1 else 0.0,
                return_2d=return_pct if horizon_days == 2 else 0.0,
                return_3d=return_pct if horizon_days == 3 else 0.0,
                return_4d=return_pct if horizon_days == 4 else 0.0,
                return_5d=return_pct if horizon_days == 5 else 0.0,
                max_gain_5d=float(outcome.max_gain_pct or 0.0),
                max_drawdown_5d=float(outcome.max_drawdown_pct or 0.0),
                entry_zone_low=float(ledger.entry_zone_low or 0.0),
                entry_zone_high=float(ledger.entry_zone_high or 0.0),
                entry_trade_date=outcome.return_start_time.date().isoformat() if outcome.return_start_time else "",
                exit_trade_date=outcome.return_start_time.date().isoformat() if outcome.return_start_time else "",
                market_state=str(ledger.market_regime or ""),
                sector_name="",
                production_score=float(ledger.production_score or 0.0) if ledger.production_score is not None else None,
                front_row_tier=str(ledger.front_row_tier or "unknown"),
                data_cutoff_time=ledger.data_cutoff_time.isoformat() if ledger.data_cutoff_time else "",
                return_start_time=ledger.return_start_time.isoformat() if ledger.return_start_time else "",
            )
        )
    return outcomes


def _pct(price: float, base: float) -> float:
    return round((price - base) / base * 100.0, 4) if base > 0 else 0.0
