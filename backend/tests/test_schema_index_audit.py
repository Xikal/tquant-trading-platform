from __future__ import annotations

from sqlalchemy import Column, Date, Float, Integer, MetaData, String, Table, create_engine

from scripts.schema_index_audit import EXPECTED_INDEXES, audit_schema_indexes


def test_expected_indexes_include_priority_board_hot_path() -> None:
    assert any(
        spec.table == "low_buy_result_snapshots"
        and spec.columns == ("latest_trade_date", "strategy_key", "score")
        for spec in EXPECTED_INDEXES
    )


def test_schema_index_audit_reports_missing_indexes(tmp_path) -> None:
    db_path = tmp_path / "audit.sqlite"
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    metadata = MetaData()
    Table(
        "low_buy_result_snapshots",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("latest_trade_date", Date),
        Column("strategy_key", String(80)),
        Column("buy_signal_state", String(40)),
        Column("symbol", String(16)),
        Column("score", Float),
    )
    metadata.create_all(engine)

    report = audit_schema_indexes(f"sqlite:///{db_path}")

    assert report["status"] == "degraded"
    assert report["missing_index_count"] >= 1
    assert any(item["table"] == "low_buy_result_snapshots" for item in report["missing_indexes"])
