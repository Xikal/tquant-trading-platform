from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.schema_defs.phase4 import RuntimeTaskCreate
from app.services.tasks import RuntimeTaskQueue
from app.services.tasks.registry import analytics_task_registry
from app.services.tasks import worker as worker_module
from app.models.entities import DailyBarSnapshot, ProductionSignalLedger, SignalRealizedOutcome
from app.services.track_record.realized_outcome import (
    compute_portfolio_realized_metrics,
    refresh_realized_outcomes,
)


def test_refresh_realized_outcomes_uses_post_signal_bars_and_settles_horizons() -> None:
    Session = _session_factory()
    with Session() as db:
        ledger = _ledger()
        db.add(ledger)
        db.flush()
        db.add_all(
            [
                _bar("600000", date(2026, 6, 1), close_price=10.0, high_price=10.4, low_price=9.9),
                _bar("600000", date(2026, 6, 2), close_price=10.5, high_price=10.8, low_price=10.2),
                _bar("600000", date(2026, 6, 3), close_price=10.8, high_price=11.2, low_price=10.1),
                _bar("600000", date(2026, 6, 4), close_price=11.0, high_price=11.3, low_price=10.6),
                _bar("600000", date(2026, 6, 5), close_price=11.5, high_price=11.8, low_price=10.9),
            ]
        )
        result = refresh_realized_outcomes(db, as_of=date(2026, 6, 6), horizons=[1, 3, 5])
        db.commit()

        outcomes = db.execute(
            select(SignalRealizedOutcome).order_by(SignalRealizedOutcome.horizon_days.asc())
        ).scalars().all()

    assert result["settled"] == 3
    assert result["unsettled"] == 0
    assert [item.horizon_days for item in outcomes] == [1, 3, 5]
    assert [round(float(item.return_pct or 0), 4) for item in outcomes] == [0.0, 8.0, 15.0]
    assert outcomes[0].return_start_time == datetime(2026, 6, 1, 9, 30)
    assert outcomes[2].max_gain_pct == 18.0
    assert outcomes[2].max_drawdown_pct == -1.0
    assert outcomes[2].settled is True


def test_refresh_realized_outcomes_marks_missing_future_data_unsettled() -> None:
    Session = _session_factory()
    with Session() as db:
        ledger = _ledger()
        db.add(ledger)
        db.add(_bar("600000", date(2026, 6, 1), close_price=10.0))
        result = refresh_realized_outcomes(db, as_of=date(2026, 6, 2), horizons=[3])
        db.commit()
        outcome = db.execute(select(SignalRealizedOutcome)).scalar_one()

    assert result["settled"] == 0
    assert result["unsettled"] == 1
    assert outcome.settled is False
    assert outcome.return_pct is None
    assert outcome.data_quality == "missing"


def test_compute_portfolio_realized_metrics_reuses_backtest_portfolio_engine(monkeypatch) -> None:
    Session = _session_factory()
    called: dict[str, object] = {}

    def fake_portfolio_backtest_metrics(outcomes, *, max_positions, states=None, **kwargs):  # noqa: ANN001
        called["count"] = len(outcomes)
        called["max_positions"] = max_positions
        called["states"] = states
        called["kwargs"] = kwargs
        return {"capital_model": f"fake-max{max_positions}", "trade_count": len(outcomes)}

    monkeypatch.setattr(
        "app.services.track_record.realized_outcome.portfolio_backtest_metrics",
        fake_portfolio_backtest_metrics,
    )
    with Session() as db:
        ledger = _ledger()
        db.add(ledger)
        db.flush()
        db.add(
            SignalRealizedOutcome(
                ledger_id=ledger.id,
                horizon_days=5,
                return_pct=5.0,
                max_gain_pct=6.0,
                max_drawdown_pct=-1.0,
                exit_reason="horizon_5d",
                return_start_time=ledger.return_start_time,
                settled=True,
                data_quality="ok",
            )
        )
        db.commit()
        result = compute_portfolio_realized_metrics(db, max_positions=5)

    assert result["capital_model"] == "fake-max5"
    assert called["count"] == 1
    assert called["max_positions"] == 5
    assert called["states"] == {"buy_now", "soft_buy_now"}


def test_analytics_worker_consumes_realized_outcome_refresh(monkeypatch) -> None:
    Session = _session_factory()
    calls: list[dict[str, object]] = []

    def fake_refresh_realized_outcomes(db, *, as_of, horizons):  # noqa: ANN001
        calls.append({"db": db, "as_of": as_of, "horizons": horizons})
        return {"ok": True, "settled": 2, "unsettled": 1}

    monkeypatch.setattr(
        "app.services.track_record.realized_outcome.refresh_realized_outcomes",
        fake_refresh_realized_outcomes,
    )
    monkeypatch.setattr(worker_module, "SessionLocal", Session)
    with Session() as db:
        task = RuntimeTaskQueue(db).enqueue(
            RuntimeTaskCreate(
                task_type="realized_outcome_refresh",
                payload={"as_of_date": "2026-06-06", "horizons": [1, 5]},
                priority=10,
            )
        )

    worker = worker_module.RuntimeTaskWorker(
        registry=analytics_task_registry(),
        worker_id="pytest-analytics",
        poll_interval_seconds=0.01,
    )
    assert worker.run_once() is True
    with Session() as db:
        stored = RuntimeTaskQueue(db).get(task.id)

    assert stored.status == "succeeded"
    assert stored.result["ok"] is True
    assert stored.result["worker_scope"] == "analytics-worker"
    assert stored.result["task_type"] == "realized_outcome_refresh"
    assert calls == [{"db": calls[0]["db"], "as_of": date(2026, 6, 6), "horizons": [1, 5]}]


def _session_factory():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)


def _ledger() -> ProductionSignalLedger:
    return ProductionSignalLedger(
        signal_date=date(2026, 5, 29),
        strategy_key="first_board",
        symbol="600000",
        name="浦发银行",
        signal_state="buy_now",
        production_score=88.0,
        priority_score=91.0,
        entry_zone_low=9.8,
        entry_zone_high=10.2,
        stop_loss=9.5,
        expected_horizon_returns_json='{"5": 2.0}',
        market_regime="strong",
        front_row_tier="core_leader",
        data_quality="ok",
        signal_time=datetime(2026, 5, 29, 15, 1),
        data_cutoff_time=datetime(2026, 5, 29, 15, 0),
        return_start_time=datetime(2026, 6, 1, 9, 30),
        source_version="unit-test",
    )


def _bar(
    symbol: str,
    trade_date: date,
    *,
    close_price: float,
    high_price: float | None = None,
    low_price: float | None = None,
) -> DailyBarSnapshot:
    return DailyBarSnapshot(
        symbol=symbol,
        market="CN",
        instrument_type="stock",
        trade_date=trade_date,
        open_price=close_price,
        close_price=close_price,
        high_price=high_price if high_price is not None else close_price,
        low_price=low_price if low_price is not None else close_price,
        volume=100000,
        amount=1000000,
        data_quality="ok",
    )
