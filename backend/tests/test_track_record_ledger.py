from __future__ import annotations

import json
from datetime import date, datetime, timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import AppSettings
from app.models.base import Base
from app.models.schemas import LowBuyPriorityBoardItemOut
from app.models.track_record_entities import (
    ProductionSignalLedger,
    SignalRealizedOutcome,
    StrategyDriftSnapshot,
)
from app.services.track_record.signal_ledger import capture_production_signals
from app.workers import runtime_worker


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


def test_capture_production_signals_keeps_only_buy_class_production_items() -> None:
    Session = _session_factory()
    with Session() as db:
        result = capture_production_signals(
            db,
            [
                _priority_item("600000", strategy_key="first_board", signal_state="buy_now", production_score=88.0),
                _priority_item("600001", strategy_key="volume_shrink", signal_state="soft_buy_now", production_score=78.0),
                _priority_item("600002", strategy_key="first_board", signal_state="near_entry", production_score=None),
                _priority_item("600003", strategy_key="n_pattern_long_wash", signal_state="buy_now", production_score=None),
                _priority_item("300750", strategy_key="first_board", signal_state="buy_now", production_score=90.0),
            ],
            as_of=date(2026, 5, 29),
            signal_time=datetime(2026, 5, 29, 15, 1),
            data_cutoff_time=datetime(2026, 5, 29, 15, 0),
            return_start_time=datetime(2026, 6, 1, 9, 30),
        )
        db.commit()

        rows = db.execute(select(ProductionSignalLedger).order_by(ProductionSignalLedger.symbol.asc())).scalars().all()

    assert result == {
        "ok": True,
        "captured": 2,
        "skipped": 3,
        "duplicates": 0,
        "watch_only": 1,
        "non_production": 1,
        "excluded_board": 1,
    }
    assert [row.symbol for row in rows] == ["600000", "600001"]
    assert rows[0].signal_time == datetime(2026, 5, 29, 15, 1)
    assert rows[0].data_cutoff_time == datetime(2026, 5, 29, 15, 0)
    assert rows[0].return_start_time == datetime(2026, 6, 1, 9, 30)
    assert json.loads(rows[0].expected_horizon_returns_json) == {
        "1": 0.4,
        "2": 0.8,
        "3": 1.2,
        "4": 1.6,
        "5": 2.0,
        "avg_net_return_pct": 1.1,
        "profit_factor": 1.7,
        "sample_settled": 42,
    }


def test_capture_production_signals_is_append_only_without_duplicate_rewrites() -> None:
    Session = _session_factory()
    item = _priority_item("600000", strategy_key="first_board", signal_state="buy_now", production_score=88.0)
    with Session() as db:
        first = capture_production_signals(
            db,
            [item],
            as_of=date(2026, 5, 29),
            signal_time=datetime(2026, 5, 29, 15, 1),
            data_cutoff_time=datetime(2026, 5, 29, 15, 0),
            return_start_time=datetime(2026, 6, 1, 9, 30),
        )
        second = capture_production_signals(
            db,
            [item.model_copy(update={"priority_score": 99.0})],
            as_of=date(2026, 5, 29),
            signal_time=datetime(2026, 5, 29, 15, 5),
            data_cutoff_time=datetime(2026, 5, 29, 15, 4),
            return_start_time=datetime(2026, 6, 1, 9, 30),
        )
        db.commit()
        rows = db.execute(select(ProductionSignalLedger)).scalars().all()

    assert first["captured"] == 1
    assert second["captured"] == 0
    assert second["duplicates"] == 1
    assert len(rows) == 1
    assert rows[0].priority_score == 91.0
    assert rows[0].data_cutoff_time == datetime(2026, 5, 29, 15, 0)


def test_signal_ledger_capture_runtime_task_is_registered(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_capture_latest_priority_board(db, *, as_of, limit):  # noqa: ANN001
        captured["db"] = db
        captured["as_of"] = as_of
        captured["limit"] = limit
        return {"ok": True, "captured": 1, "worker_scope": "runtime-worker"}

    monkeypatch.setattr(
        "app.services.track_record.signal_ledger.capture_latest_priority_board",
        fake_capture_latest_priority_board,
    )

    assert "signal_ledger_capture" in runtime_worker.RUNTIME_WORKER_TASK_TYPES
    result = runtime_worker._execute_task(
        "signal_ledger_capture",
        {"as_of_date": "2026-05-29", "limit": 7},
        object(),
    )

    assert result["ok"] is True
    assert result["captured"] == 1
    assert result["worker_scope"] == "runtime-worker"
    assert result["gate_owner"] == "production-track-record"
    assert captured["as_of"] == date(2026, 5, 29)
    assert captured["limit"] == 7


def _session_factory():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)


def _priority_item(
    symbol: str,
    *,
    strategy_key: str,
    signal_state: str,
    production_score: float | None,
) -> LowBuyPriorityBoardItemOut:
    return LowBuyPriorityBoardItemOut(
        symbol=symbol,
        name=f"{symbol}测试",
        sector_name="银行",
        strategy_key=strategy_key,
        strategy_title=strategy_key,
        latest_price=10.5,
        change_pct=1.2,
        quote_timestamp="2026-05-29 15:00:00",
        data_quality="ok",
        market_state_category="strong",
        market_state_category_text="强势",
        buy_signal_state=signal_state,
        buy_signal_text=signal_state,
        priority_score=91.0,
        entry_zone_low=10.2,
        entry_zone_high=10.8,
        stop_loss=9.7,
        production_score=production_score,
        front_row_tier="core_leader",
        strategy_performance_text="近样本42，PF 1.7，5日均值2.0%",
        score_components={"base": 50.0},
        expected_horizon_returns={"1": 0.4, "2": 0.8, "3": 1.2, "4": 1.6, "5": 2.0},
        expected_avg_return_pct=1.1,
        expected_profit_factor=1.7,
        expected_sample_settled=42,
    )
