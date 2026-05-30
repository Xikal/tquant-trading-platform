from __future__ import annotations

from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import AppSettings
from app.models.base import Base
from app.models.schema_defs.decision_context import DecisionContextOut, GateDecisionOut
from app.services.decision_context.snapshot_writer import DecisionContextSnapshotWriter


def test_decision_context_requires_all_core_gates() -> None:
    payload = DecisionContextOut(
        symbol="000001",
        trade_date=date(2026, 5, 29),
        strategy_key="first_board",
        strategy_tier="core",
        production_eligible=True,
        market_gate=GateDecisionOut(decision="allow", score=82.0, reasons=["强势修复"]),
        sector_leader_gate=GateDecisionOut(decision="allow", score=76.0, reasons=["板块扩散"]),
        hard_risk_gate=GateDecisionOut(decision="allow", score=100.0, reasons=[]),
        event_risk_gate=GateDecisionOut(decision="allow", score=100.0, reasons=[]),
        intraday_entry_gate=GateDecisionOut(decision="wait", score=55.0, reasons=["等待回踩 VWAP"]),
        final_decision="candidate",
        final_score=78.5,
        data_quality="ok",
    )

    assert payload.final_decision == "candidate"


def test_decision_context_feature_flags_are_declared() -> None:
    settings = AppSettings()

    assert settings.decision_context_enabled is True
    assert settings.market_gate_production_enabled is True
    assert settings.hard_risk_filter_production_enabled is True


def test_decision_context_writer_upserts_and_reads_latest() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)
    context = DecisionContextOut(
        symbol="000001",
        trade_date=date(2026, 5, 29),
        strategy_key="first_board",
        strategy_tier="core",
        production_eligible=True,
        market_gate=GateDecisionOut(decision="allow", score=82.0, reasons=["强势修复"]),
        sector_leader_gate=GateDecisionOut(decision="research_only", score=0.0, reasons=["Batch B 未启用"]),
        hard_risk_gate=GateDecisionOut(decision="allow", score=100.0, reasons=[]),
        event_risk_gate=GateDecisionOut(decision="research_only", score=0.0, reasons=["Batch C 未启用"]),
        intraday_entry_gate=GateDecisionOut(decision="research_only", score=0.0, reasons=["Batch C 未启用"]),
        final_decision="front_row",
        final_score=88.0,
        data_quality="ok",
    )
    updated = context.model_copy(update={"final_score": 90.0})

    with Session() as db:
        writer = DecisionContextSnapshotWriter(db)
        first_id = writer.upsert_context(context, source_snapshot={"source": "test"})
        second_id = writer.upsert_context(updated, source_snapshot={"source": "test-updated"})
        latest = writer.latest_for_symbol("000001", strategy_key="first_board")
        board = writer.latest_board(trade_date=date(2026, 5, 29), limit=10)

    assert second_id == first_id
    assert latest is not None
    assert latest.final_score == 90.0
    assert len(board) == 1
    assert board[0].symbol == "000001"
