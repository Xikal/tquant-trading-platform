from __future__ import annotations

import json
from datetime import date, datetime, timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import AppSettings
from app.models.base import Base
from app.models.track_record_entities import (
    ProductionSignalLedger,
    SignalRealizedOutcome,
    StrategyDriftSnapshot,
)


def test_track_record_schema_roundtrip_and_flags() -> None:
    settings = AppSettings()
    assert settings.track_record_enabled is True
    assert settings.drift_alert_enabled is False

    Session = _session_factory()
    with Session() as db:
        ledger = ProductionSignalLedger(
            signal_date=date(2026, 5, 29),
            strategy_key="first_board",
            symbol="600000",
            name="浦发银行",
            signal_state="buy_now",
            production_score=88.2,
            priority_score=91.3,
            entry_zone_low=10.2,
            entry_zone_high=10.8,
            stop_loss=9.7,
            expected_horizon_returns_json=json.dumps({"1": 1.2, "3": 2.4, "5": 4.1}, ensure_ascii=False),
            market_regime="strong",
            front_row_tier="core_leader",
            data_quality="ok",
            signal_time=datetime(2026, 5, 29, 14, 58),
            data_cutoff_time=datetime(2026, 5, 29, 14, 57),
            return_start_time=datetime(2026, 6, 1, 9, 30),
            source_version="unit-test",
        )
        db.add(ledger)
        db.flush()
        db.add(
            SignalRealizedOutcome(
                ledger_id=ledger.id,
                horizon_days=5,
                return_pct=3.4,
                max_gain_pct=5.1,
                max_drawdown_pct=-1.2,
                exit_reason="horizon_5d",
                return_start_time=ledger.return_start_time,
                settled=True,
                data_quality="ok",
            )
        )
        db.add(
            StrategyDriftSnapshot(
                strategy_key="first_board",
                as_of_date=date(2026, 6, 5),
                window_days=60,
                realized_pf=1.8,
                expected_pf=2.0,
                realized_avg=1.1,
                expected_avg=1.3,
                realized_winrate=58.0,
                expected_winrate=60.0,
                realized_max5=4.4,
                backtest_max5=4.8,
                realized_max10=6.2,
                backtest_max10=7.0,
                tracking_error=0.7,
                decay_pct=-10.0,
                drift_flag="ok",
                sample_settled=30,
            )
        )
        db.commit()

    with Session() as db:
        stored = db.execute(select(ProductionSignalLedger)).scalar_one()
        outcome = db.execute(select(SignalRealizedOutcome)).scalar_one()
        drift = db.execute(select(StrategyDriftSnapshot)).scalar_one()

    assert stored.signal_time <= stored.data_cutoff_time + timedelta(minutes=1)
    assert stored.return_start_time > stored.signal_time
    assert json.loads(stored.expected_horizon_returns_json)["5"] == 4.1
    assert outcome.ledger_id == stored.id
    assert outcome.settled is True
    assert drift.sample_settled == 30


def test_track_record_schema_enforces_unique_signal_identity() -> None:
    Session = _session_factory()
    with Session() as db:
        first = ProductionSignalLedger(
            signal_date=date(2026, 5, 29),
            strategy_key="first_board",
            symbol="600000",
            signal_state="buy_now",
            signal_time=datetime(2026, 5, 29, 14, 58),
            data_cutoff_time=datetime(2026, 5, 29, 14, 57),
            return_start_time=datetime(2026, 6, 1, 9, 30),
        )
        duplicate = ProductionSignalLedger(
            signal_date=date(2026, 5, 29),
            strategy_key="first_board",
            symbol="600000",
            signal_state="buy_now",
            signal_time=datetime(2026, 5, 29, 15, 0),
            data_cutoff_time=datetime(2026, 5, 29, 14, 59),
            return_start_time=datetime(2026, 6, 1, 9, 30),
        )
        db.add(first)
        db.commit()
        db.add(duplicate)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
        else:
            raise AssertionError("duplicate production signal ledger row should violate unique identity")


def _session_factory():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)
