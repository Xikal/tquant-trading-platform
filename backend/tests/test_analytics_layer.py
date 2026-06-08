from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.entities import (
    AnalysisLog,
    BacktestDailySnapshot,
    BacktestRun,
    BacktestTrade,
    DailyBarSnapshot,
    KeyLevelSnapshot,
    LowBuyResultSnapshot,
    MarketReviewReport,
    PaperReviewReport,
    RuntimeTask,
    StrategyTrackingSnapshot,
)
from app.services.analytics.duckdb_repository import DuckDBRepository
from app.services.analytics.exporters import (
    export_analysis_logs_parquet,
    export_daily_bars_parquet,
    export_key_level_snapshots_parquet,
    export_low_buy_result_snapshots_parquet,
    export_market_review_reports_parquet,
    export_paper_review_reports_parquet,
    export_strategy_tracking_snapshots_parquet,
)
from app.services.analytics.backtest_exporters import (
    export_backtest_daily_snapshots_parquet,
    export_backtest_runs_parquet,
    export_backtest_trades_parquet,
)
from app.services.analytics.manifest import load_manifest
from app.services.analytics.quality import check_daily_bars_24m_quality
from app.services.analytics.report_queries import build_strategy_24m_duckdb_report
from app.services.backtest.parquet_data_provider import DailyBarParquetDataProvider


def _db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()


def test_quality_creates_backfill_task_when_24m_data_incomplete(tmp_path):
    db = _db()
    db.add(_bar("000001", date(2026, 5, 29)))
    db.commit()

    quality = check_daily_bars_24m_quality(
        db,
        months=24,
        end_date=date(2026, 5, 30),
        min_symbols_per_day=1,
        create_backfill_task=True,
    )

    assert quality.status == "fail"
    assert "daily_bars_start_after_required_window" in quality.blockers
    assert quality.backfill_task_id is not None
    task = db.get(RuntimeTask, quality.backfill_task_id)
    assert task is not None
    assert task.task_type == "data_backfill_24m"


def test_export_writes_parquet_and_manifest_with_failure_quality(tmp_path):
    db = _db()
    for offset in range(3):
        db.add(_bar("000001", date(2026, 5, 27) + timedelta(days=offset)))
    db.commit()

    manifest = export_daily_bars_parquet(
        db,
        months=24,
        end_date=date(2026, 5, 30),
        output_root=tmp_path,
        create_backfill_task=True,
    )

    assert manifest["dataset_key"] == "daily_bars"
    assert manifest["row_count"] == 3
    assert manifest["quality"]["status"] == "fail"
    assert manifest["quality"]["backfill_task_id"] is not None
    assert manifest["files"]
    loaded = load_manifest(manifest["manifest_path"])
    assert loaded["dataset_version"] == manifest["dataset_version"]
    assert loaded["manifest_id"] == manifest["manifest_id"]
    assert loaded["valid_until"]


def test_daily_bar_parquet_provider_reads_exported_bars_and_manifest(tmp_path):
    db = _db()
    for offset, close in enumerate([10.5, 10.8]):
        db.add(_bar("000001", date(2026, 5, 27) + timedelta(days=offset), close_price=close))
    db.commit()
    manifest = export_daily_bars_parquet(
        db,
        months=1,
        end_date=date(2026, 5, 28),
        output_root=tmp_path,
        create_backfill_task=False,
    )

    provider = DailyBarParquetDataProvider(db, output_root=tmp_path, manifest=manifest["manifest_path"])

    assert provider.fetch_trade_dates("2026-05-27", "2026-05-28") == ["2026-05-27", "2026-05-28"]
    histories = provider.fetch_bars(["000001"], start_date="2026-05-27", end_date="2026-05-28")
    assert [bar.close_price for bar in histories["000001"]] == [10.5, 10.8]
    dataset = provider.dataset_manifest(start_date="2026-05-27", end_date="2026-05-28", symbols=["000001"])
    assert dataset["storage"] == "parquet"
    assert dataset["manifest_id"] == manifest["manifest_id"]


def test_quality_coverage_pct_is_capped_and_extra_days_are_explicit(tmp_path):
    db = _db()
    for offset in range(31):
        db.add(_bar("000001", date(2025, 12, 6) + timedelta(days=offset)))
    db.commit()

    quality = check_daily_bars_24m_quality(
        db,
        months=1,
        end_date=date(2026, 1, 5),
        min_symbols_per_day=1,
        create_backfill_task=False,
    )
    payload = quality.as_dict()

    assert payload["actual_trade_days"] > payload["required_trade_days"]
    assert payload["coverage_pct"] == 100.0
    assert payload["coverage_pct"] <= 100.0
    assert payload["over_coverage_trade_days"] == payload["actual_trade_days"] - payload["required_trade_days"]
    assert payload["required_start"] == payload["period_start"]
    assert payload["required_end"] == payload["period_end"]


def test_manifest_coverage_uses_capped_semantics(tmp_path):
    db = _db()
    for offset in range(31):
        db.add(_bar("000001", date(2025, 12, 6) + timedelta(days=offset)))
    db.commit()

    manifest = export_daily_bars_parquet(
        db,
        months=1,
        end_date=date(2026, 1, 5),
        output_root=tmp_path,
        create_backfill_task=False,
    )

    assert manifest["coverage"]["coverage_pct"] <= 100.0
    assert manifest["coverage"]["coverage_pct"] == manifest["quality"]["coverage_pct"]
    assert manifest["coverage"]["over_coverage_trade_days"] == manifest["quality"]["over_coverage_trade_days"]
    assert manifest["coverage"]["required_trade_days"] == manifest["quality"]["required_trade_days"]


def test_duckdb_report_normalizes_legacy_manifest_coverage(tmp_path):
    db = _db()
    for offset in range(31):
        db.add(_bar("000001", date(2025, 12, 6) + timedelta(days=offset)))
    db.commit()
    manifest = export_daily_bars_parquet(
        db,
        months=1,
        end_date=date(2026, 1, 5),
        output_root=tmp_path,
        create_backfill_task=False,
    )
    legacy_manifest = dict(manifest)
    legacy_manifest["quality"] = {
        key: value
        for key, value in dict(manifest["quality"]).items()
        if key
        not in {
            "required_trade_days",
            "actual_trade_days",
            "complete_trade_days",
            "missing_trade_days",
            "over_coverage_trade_days",
            "coverage_status",
            "coverage_pct",
        }
    }
    legacy_manifest["quality"]["coverage_pct"] = 140.0
    legacy_manifest["quality"]["complete_coverage_pct"] = 125.0

    report = build_strategy_24m_duckdb_report(legacy_manifest, output_root=tmp_path)
    quality = report["manifest"]["quality"]

    assert quality["coverage_pct"] == 100.0
    assert quality["complete_coverage_pct"] <= 100.0
    assert quality["over_coverage_trade_days"] > 0
    assert quality["required_trade_days"] > 0


def test_export_strategy_tracking_snapshots_writes_manifest_and_duckdb_readable_parquet(tmp_path):
    db = _db()
    db.add(
        StrategyTrackingSnapshot(
            snapshot_key="range:60:all",
            as_of_date="2026-06-08",
            range_days=60,
            strategy_key="first_board",
            strategy_family="low_buy",
            market_scope="all",
            filter_hash="abc",
            data_version="v1",
            status="fresh",
            payload_json='{"items":[]}',
            metrics_json='{"total":1}',
        )
    )
    db.commit()

    manifest = export_strategy_tracking_snapshots_parquet(
        db,
        days=7,
        end_date=date(2026, 6, 8),
        output_root=tmp_path,
    )

    assert manifest["dataset_key"] == "strategy_tracking_snapshots"
    assert manifest["source"]["source_table"] == "strategy_tracking_snapshots"
    assert manifest["row_count"] == 1
    assert manifest["quality_status"] == "ok"
    assert manifest["files"]

    parquet_glob = str(tmp_path / "parquet" / "strategy_tracking_snapshots" / "**" / "*.parquet")
    repo = DuckDBRepository(output_root=tmp_path, threads=1)
    try:
        row = repo.query_one(f"SELECT count(*) AS row_count, max(strategy_key) AS strategy_key FROM read_parquet('{parquet_glob}')")
    finally:
        repo.close()
    assert row == {"row_count": 1, "strategy_key": "first_board"}


def test_export_strategy_tracking_snapshots_no_data_manifest_is_explicit(tmp_path):
    db = _db()

    manifest = export_strategy_tracking_snapshots_parquet(
        db,
        days=7,
        end_date=date(2026, 6, 8),
        output_root=tmp_path,
    )

    assert manifest["dataset_key"] == "strategy_tracking_snapshots"
    assert manifest["row_count"] == 0
    assert manifest["quality_status"] == "no_data"
    assert manifest["files"] == []
    assert manifest["quality"]["blockers"] == ["strategy_tracking_snapshots_no_rows"]


def test_export_key_level_snapshots_writes_manifest_and_parquet(tmp_path):
    db = _db()
    db.add(
        KeyLevelSnapshot(
            scope="symbol",
            cache_key="000001",
            symbol="000001",
            trade_date="2026-06-08",
            engine_version="akey-level-v1",
            data_quality="fresh",
            payload_json='{"support":10.2}',
        )
    )
    db.commit()

    manifest = export_key_level_snapshots_parquet(db, days=3, end_date=date(2026, 6, 8), output_root=tmp_path)

    assert manifest["dataset_key"] == "key_level_snapshots"
    assert manifest["source"]["source_table"] == "key_level_snapshots"
    assert manifest["row_count"] == 1
    assert manifest["quality_status"] == "ok"
    assert manifest["files"]

    repo = DuckDBRepository(output_root=tmp_path, threads=1)
    try:
        row = repo.query_one(
            f"SELECT count(*) AS row_count, max(symbol) AS symbol FROM read_parquet('{tmp_path / 'parquet' / 'key_level_snapshots' / '**' / '*.parquet'}')"
        )
    finally:
        repo.close()
    assert row == {"row_count": 1, "symbol": "000001"}


def test_export_low_buy_result_snapshots_writes_manifest_and_parquet(tmp_path):
    db = _db()
    db.add(
        LowBuyResultSnapshot(
            latest_trade_date="2026-06-08",
            strategy_key="first_board",
            symbol="000001",
            name="平安银行",
            score=88.5,
            buy_signal_state="watch",
            payload_json='{"rank":1}',
        )
    )
    db.commit()

    manifest = export_low_buy_result_snapshots_parquet(db, days=3, end_date=date(2026, 6, 8), output_root=tmp_path)

    assert manifest["dataset_key"] == "low_buy_result_snapshots"
    assert manifest["source"]["source_table"] == "low_buy_result_snapshots"
    assert manifest["row_count"] == 1
    assert manifest["quality_status"] == "ok"
    assert manifest["files"]

    repo = DuckDBRepository(output_root=tmp_path, threads=1)
    try:
        row = repo.query_one(
            f"SELECT count(*) AS row_count, max(strategy_key) AS strategy_key FROM read_parquet('{tmp_path / 'parquet' / 'low_buy_result_snapshots' / '**' / '*.parquet'}')"
        )
    finally:
        repo.close()
    assert row == {"row_count": 1, "strategy_key": "first_board"}


def test_export_backtest_runs_writes_manifest_and_duckdb_readable_parquet(tmp_path):
    db = _db()
    db.add(
        BacktestRun(
            name="低吸回测",
            status="succeeded",
            strategy_keys="first_board",
            start_date="2026-06-01",
            end_date="2026-06-08",
            initial_cash=100000,
            final_equity=103000,
            engine_version="backtest-v2",
        )
    )
    db.commit()

    manifest = export_backtest_runs_parquet(db, days=30, end_date=date(2026, 6, 8), output_root=tmp_path)

    assert manifest["dataset_key"] == "backtest_runs"
    assert manifest["source"]["source_table"] == "backtest_runs"
    assert manifest["source"]["source_date_column"] == "created_at"
    assert manifest["row_count"] == 1
    assert manifest["quality_status"] == "ok"
    assert manifest["files"]

    repo = DuckDBRepository(output_root=tmp_path, threads=1)
    try:
        row = repo.query_one(
            f"SELECT count(*) AS row_count, max(strategy_keys) AS strategy_keys FROM read_parquet('{tmp_path / 'parquet' / 'backtest_runs' / '**' / '*.parquet'}')"
        )
    finally:
        repo.close()
    assert row == {"row_count": 1, "strategy_keys": "first_board"}


def test_export_backtest_trades_and_daily_snapshots_are_duckdb_readable(tmp_path):
    db = _db()
    run = BacktestRun(
        name="组合回测",
        status="succeeded",
        strategy_keys="first_board",
        start_date="2026-06-01",
        end_date="2026-06-08",
    )
    db.add(run)
    db.flush()
    db.add(
        BacktestTrade(
            run_id=run.id,
            trade_date="2026-06-08",
            symbol="000001",
            name="平安银行",
            side="sell",
            strategy_key="first_board",
            quantity=100,
            price=11.2,
            pnl_pct=4.5,
            pnl_amount=450,
            market_state="risk_release",
        )
    )
    db.add(
        BacktestDailySnapshot(
            run_id=run.id,
            trade_date="2026-06-08",
            cash=50000,
            market_value=53000,
            equity=103000,
            daily_return_pct=3.0,
            drawdown_pct=0.0,
            exposure_pct=51.4,
            positions_count=1,
            turnover=0.2,
            benchmark_symbol="000300",
            benchmark_close=3800,
            benchmark_return_pct=1.0,
            market_state="risk_release",
        )
    )
    db.commit()

    trades_manifest = export_backtest_trades_parquet(db, days=7, end_date=date(2026, 6, 8), output_root=tmp_path)
    snapshots_manifest = export_backtest_daily_snapshots_parquet(
        db,
        days=7,
        end_date=date(2026, 6, 8),
        output_root=tmp_path,
    )

    assert trades_manifest["dataset_key"] == "backtest_trades"
    assert trades_manifest["row_count"] == 1
    assert trades_manifest["quality_status"] == "ok"
    assert snapshots_manifest["dataset_key"] == "backtest_daily_snapshots"
    assert snapshots_manifest["row_count"] == 1
    assert snapshots_manifest["quality_status"] == "ok"

    repo = DuckDBRepository(output_root=tmp_path, threads=1)
    try:
        trade = repo.query_one(
            f"SELECT count(*) AS row_count, max(symbol) AS symbol FROM read_parquet('{tmp_path / 'parquet' / 'backtest_trades' / '**' / '*.parquet'}')"
        )
        snapshot = repo.query_one(
            f"SELECT count(*) AS row_count, max(equity) AS equity FROM read_parquet('{tmp_path / 'parquet' / 'backtest_daily_snapshots' / '**' / '*.parquet'}')"
        )
    finally:
        repo.close()
    assert trade == {"row_count": 1, "symbol": "000001"}
    assert snapshot == {"row_count": 1, "equity": 103000.0}


def test_export_backtest_trades_no_data_manifest_is_explicit(tmp_path):
    db = _db()

    manifest = export_backtest_trades_parquet(db, days=7, end_date=date(2026, 6, 8), output_root=tmp_path)

    assert manifest["dataset_key"] == "backtest_trades"
    assert manifest["row_count"] == 0
    assert manifest["quality_status"] == "no_data"
    assert manifest["files"] == []
    assert manifest["quality"]["blockers"] == ["backtest_trades_no_rows"]


def test_export_analysis_and_review_reports_are_duckdb_readable(tmp_path):
    db = _db()
    db.add(
        AnalysisLog(
            symbol="000001",
            action="watch",
            signal_score=81.0,
            risk_level="medium",
            payload_json='{"source":"analysis"}',
        )
    )
    db.add(
        MarketReviewReport(
            report_date=date(2026, 6, 8),
            report_slot="close",
            overall_summary="市场复盘",
            strategy_highlights='["低吸"]',
            risk_alerts='["缩量"]',
            suggestion="观察",
            raw_metrics_snapshot='{"pulse":"neutral"}',
            llm_model="market-rule",
        )
    )
    db.add(
        PaperReviewReport(
            account_id=1,
            report_date=date(2026, 6, 8),
            report_slot="close",
            overall_summary="模拟盘复盘",
            strategy_highlights='["纪律"]',
            risk_alerts='[]',
            suggestion="控制仓位",
            raw_metrics_snapshot='{"cash":100000}',
            llm_model="paper-rule",
        )
    )
    db.commit()

    analysis_manifest = export_analysis_logs_parquet(db, days=7, end_date=date(2026, 6, 8), output_root=tmp_path)
    market_manifest = export_market_review_reports_parquet(db, days=7, end_date=date(2026, 6, 8), output_root=tmp_path)
    paper_manifest = export_paper_review_reports_parquet(db, days=7, end_date=date(2026, 6, 8), output_root=tmp_path)

    assert analysis_manifest["dataset_key"] == "analysis_logs"
    assert analysis_manifest["row_count"] == 1
    assert market_manifest["dataset_key"] == "market_review_reports"
    assert market_manifest["row_count"] == 1
    assert paper_manifest["dataset_key"] == "paper_review_reports"
    assert paper_manifest["row_count"] == 1

    repo = DuckDBRepository(output_root=tmp_path, threads=1)
    try:
        analysis = repo.query_one(
            f"SELECT count(*) AS row_count, max(symbol) AS symbol FROM read_parquet('{tmp_path / 'parquet' / 'analysis_logs' / '**' / '*.parquet'}')"
        )
        market = repo.query_one(
            f"SELECT count(*) AS row_count, max(report_slot) AS report_slot FROM read_parquet('{tmp_path / 'parquet' / 'market_review_reports' / '**' / '*.parquet'}')"
        )
        paper = repo.query_one(
            f"SELECT count(*) AS row_count, max(account_id) AS account_id FROM read_parquet('{tmp_path / 'parquet' / 'paper_review_reports' / '**' / '*.parquet'}')"
        )
    finally:
        repo.close()
    assert analysis == {"row_count": 1, "symbol": "000001"}
    assert market == {"row_count": 1, "report_slot": "close"}
    assert paper == {"row_count": 1, "account_id": 1}


def _bar(symbol: str, trade_date: date, *, close_price: float = 10.5) -> DailyBarSnapshot:
    return DailyBarSnapshot(
        symbol=symbol,
        market="CN",
        instrument_type="stock",
        trade_date=trade_date,
        open_price=10,
        high_price=11,
        low_price=9,
        close_price=close_price,
        pre_close=10,
        volume=1000,
        amount=10000,
        pct_chg=5,
        source="test",
        fetch_time="2026-05-30T00:00:00",
        adjusted_mode="qfq",
        checksum="x",
        data_quality="fresh",
    )
