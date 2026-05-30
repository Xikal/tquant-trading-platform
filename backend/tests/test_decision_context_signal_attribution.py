from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.entities import DailyBarSnapshot
from app.models.schema_defs.decision_context import DecisionContextOut, GateDecisionOut
from app.services.decision_context.signal_attribution import (
    SignalAttributionInput,
    compute_signal_outcome,
    decision_context_attribution_payload,
    refresh_signal_attributions,
)


def test_compute_signal_outcome_uses_future_bars_without_lookahead_before_entry() -> None:
    result = compute_signal_outcome(
        SignalAttributionInput(
            symbol="600000",
            entry_date=date(2026, 5, 20),
            entry_price=10.0,
            horizon_days=3,
            future_bars=[
                _bar("600000", "2026-05-21", close=10.3, high=10.5, low=9.9),
                _bar("600000", "2026-05-22", close=10.1, high=10.4, low=9.7),
                _bar("600000", "2026-05-23", close=9.8, high=10.0, low=9.6),
            ],
        )
    )

    assert result.data_quality == "ok"
    assert result.return_pct == -2.0
    assert result.max_gain_pct == 5.0
    assert result.max_drawdown_pct == -4.0
    assert result.hit is False


def test_compute_signal_outcome_marks_no_data_when_future_bars_missing() -> None:
    result = compute_signal_outcome(
        SignalAttributionInput(
            symbol="600000",
            entry_date=date(2026, 5, 20),
            entry_price=10.0,
            horizon_days=3,
            future_bars=[],
        )
    )

    assert result.data_quality == "no_data"
    assert result.return_pct is None
    assert any("缺少" in reason for reason in result.reasons)


def test_refresh_signal_attributions_writes_rows_for_existing_context() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)

    with Session() as db:
        from app.models.entities import DecisionContextSnapshot

        context = DecisionContextSnapshot(
            trade_date=date(2026, 5, 20),
            strategy_key="first_board",
            symbol="600000",
            strategy_tier="core",
            production_eligible=True,
            final_decision="front_row",
            final_score=88.0,
            data_quality="ok",
            source_snapshot_json='{"entry_price": 10.0}',
        )
        db.add(context)
        for offset, close in enumerate([10.2, 10.1, 9.8], start=1):
            db.add(_bar("600000", date(2026, 5, 20) + timedelta(days=offset), close=close, high=max(close, 10.4), low=min(close, 9.7)))
        db.commit()

        result = refresh_signal_attributions(db, as_of_date=date(2026, 5, 24), horizons=[3], limit=20)

    assert result["ok"] is True
    assert result["written_count"] == 1
    assert result["no_data_count"] == 0
    assert result["items"][0]["return_pct"] == -2.0


def test_decision_context_attribution_payload_includes_gates_and_outcomes() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)

    with Session() as db:
        from app.services.decision_context.snapshot_writer import DecisionContextSnapshotWriter

        context = DecisionContextOut(
            symbol="600000",
            trade_date=date(2026, 5, 20),
            strategy_key="first_board",
            strategy_tier="core",
            production_eligible=True,
            market_gate=GateDecisionOut(decision="allow", score=90.0, reasons=["市场修复"]),
            sector_leader_gate=GateDecisionOut(decision="reduce", score=62.0, reasons=["板块扩散不足"]),
            hard_risk_gate=GateDecisionOut(decision="allow", score=100.0, reasons=[]),
            event_risk_gate=GateDecisionOut(decision="no_data", score=0.0, reasons=["事件源缺失"]),
            intraday_entry_gate=GateDecisionOut(decision="no_data", score=0.0, reasons=["分钟数据缺失"]),
            final_decision="front_row",
            final_score=82.5,
            data_quality="ok",
        )
        context_id = DecisionContextSnapshotWriter(db).upsert_context(context, source_snapshot={"entry_price": 10.0})
        db.add(_bar("600000", "2026-05-21", close=10.4, high=10.5, low=9.8))
        db.commit()
        refresh_signal_attributions(db, as_of_date=date(2026, 5, 22), horizons=[1], limit=10)

        payload = decision_context_attribution_payload(
            db,
            symbol="600000",
            strategy_key="first_board",
            trade_date=date(2026, 5, 20),
        )

    assert payload["context_snapshot_id"] == context_id
    assert payload["production_eligible"] is True
    assert payload["strategy_tier"] == "core"
    assert payload["final_decision"] == "front_row"
    assert payload["gates"]["event_risk_gate"]["decision"] == "no_data"
    assert payload["outcomes"][0]["horizon_days"] == 1
    assert payload["outcomes"][0]["return_pct"] == 4.0


def _bar(symbol: str, trade_date: str | date, *, close: float, high: float, low: float) -> DailyBarSnapshot:
    return DailyBarSnapshot(
        symbol=symbol,
        trade_date=trade_date,
        open_price=10.0,
        close_price=close,
        high_price=high,
        low_price=low,
        volume=1000,
        amount=10000,
    )
