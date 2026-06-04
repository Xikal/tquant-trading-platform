from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.schema_compat import ensure_schema_compatibility
from app.models.base import Base
from app.models.entities import DailyBarSnapshot, InstrumentIndustryHistory
from app.models.schemas import KlineBar, QuoteSnapshot
from app.repositories.low_buy import DailyBarRow, DailyHistoryRepository
from app.services.market.minute_bar_store import MinuteBarSnapshotStore
from backend.scripts import backfill_daily_history
from backend.scripts import backfill_instrument_metadata
from backend.scripts.clean_invalid_daily_bars import clean_invalid_daily_bars


def test_schema_compat_adds_daily_and_minute_lineage_columns() -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE daily_bar_snapshots (id INTEGER PRIMARY KEY, symbol VARCHAR(16), trade_date DATE)"))
        connection.execute(text("CREATE TABLE minute_bar_snapshots (id INTEGER PRIMARY KEY, symbol VARCHAR(16), bar_timestamp VARCHAR(32))"))

    ensure_schema_compatibility(engine)

    inspector = inspect(engine)
    daily_columns = {item["name"] for item in inspector.get_columns("daily_bar_snapshots")}
    minute_columns = {item["name"] for item in inspector.get_columns("minute_bar_snapshots")}
    assert {"source", "fetch_time", "adjusted_mode", "checksum", "data_quality"} <= daily_columns
    assert {"source", "fetch_time", "checksum", "data_quality"} <= minute_columns
    assert {"limit_up_price", "limit_down_price", "is_suspended", "is_st", "is_delisted"} <= daily_columns
    assert {"bid_ask_spread", "premium_discount_pct", "tracking_index_symbol", "liquidity_tier"} <= minute_columns


def test_schema_compat_adds_instrument_lifecycle_and_history_tables() -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE instruments (id INTEGER PRIMARY KEY, symbol VARCHAR(16), name VARCHAR(64), instrument_type VARCHAR(16), sector_name VARCHAR(64))"))

    ensure_schema_compatibility(engine)

    inspector = inspect(engine)
    instrument_columns = {item["name"] for item in inspector.get_columns("instruments")}
    assert {"listing_date", "delisting_date", "is_st", "status"} <= instrument_columns
    assert "instrument_industry_history" in inspector.get_table_names()
    assert "instrument_concept_history" in inspector.get_table_names()


def test_daily_history_repository_persists_lineage_fields() -> None:
    db = _session()
    row = DailyBarRow(
        trade_date="2026-04-28",
        open_price=10,
        close_price=10.2,
        high_price=10.5,
        low_price=9.8,
        volume=1000,
        amount=10000,
        pct_chg=2,
        limit_up_price=11,
        limit_down_price=9,
        source="akshare.stock_zh_a_hist",
        adjusted_mode="qfq",
        data_quality="fresh",
    )

    DailyHistoryRepository(db).upsert_rows("000001", [row])
    db.commit()

    stored = db.query(DailyBarSnapshot).filter_by(symbol="000001").one()
    assert stored.source == "akshare.stock_zh_a_hist"
    assert stored.adjusted_mode == "qfq"
    assert stored.data_quality == "fresh"
    assert stored.limit_up_price == 11
    assert stored.limit_down_price == 9
    assert stored.is_suspended is False
    assert len(stored.checksum) == 64
    assert stored.fetch_time


def test_minute_bar_store_persists_lineage_fields(monkeypatch) -> None:
    db = _session()
    monkeypatch.setattr(
        "app.services.market.minute_bar_store.beijing_now",
        lambda: datetime(2026, 4, 28, 15, 35, 0),
    )
    quote = QuoteSnapshot(
        symbol="510300",
        name="沪深300ETF",
        market="SH",
        instrument_type="etf",
        last_price=4.0,
        change_pct=0,
        change_amount=0,
        open_price=4.0,
        high_price=4.1,
        low_price=3.9,
        prev_close=4.0,
        volume=1000,
        amount=4000,
        timestamp="2026-04-28 09:31:00",
        data_source="akshare.stock_zh_a_minute",
        data_quality="fresh",
    )

    MinuteBarSnapshotStore(db).persist(
        quote,
        [
            KlineBar(
                timestamp="2026-04-28 09:31",
                open=4,
                high=4.1,
                low=3.9,
                close=4.05,
                volume=1000,
                amount=4050,
                bid_ask_spread=0.002,
                premium_discount_pct=0.01,
                tracking_index_symbol="沪深300",
                liquidity_tier="sufficient",
            )
        ],
    )
    row = MinuteBarSnapshotStore(db).list_bars(symbol="510300", trade_date="2026-04-28")[0]

    assert row.source == "akshare.stock_zh_a_minute"
    assert row.data_quality == "fresh"
    assert row.bid_ask_spread == 0.002
    assert row.premium_discount_pct == 0.01
    assert row.tracking_index_symbol == "沪深300"
    assert row.liquidity_tier == "sufficient"
    assert len(row.checksum) == 64
    assert row.fetch_time == "2026-04-28T15:35:00"


def test_minute_bar_store_can_backfill_older_history() -> None:
    db = _session()
    quote = QuoteSnapshot(
        symbol="510300",
        name="沪深300ETF",
        market="SH",
        instrument_type="etf",
        last_price=4.0,
        change_pct=0,
        change_amount=0,
        open_price=4.0,
        high_price=4.1,
        low_price=3.9,
        prev_close=4.0,
        volume=1000,
        amount=4000,
        timestamp="2026-04-28 09:31:00",
        data_source="eastmoney.etf_minute",
        data_quality="fresh",
    )
    store = MinuteBarSnapshotStore(db)

    assert store.persist(quote, [KlineBar(timestamp="2026-04-28 09:31", open=4, high=4.1, low=3.9, close=4.05, volume=1000, amount=4050)]) == 1
    assert store.persist(
        quote,
        [KlineBar(timestamp="2026-04-27 09:31", open=3.9, high=4.0, low=3.8, close=3.95, volume=900, amount=3555)],
        skip_older_than_latest=False,
    ) == 1
    rows = store.list_bars(symbol="510300", trade_date="2026-04-27")

    assert len(rows) == 1
    assert rows[0].bar_timestamp == "2026-04-27 09:31"


def test_backfill_report_records_partial_data_and_failures(tmp_path) -> None:
    report = backfill_daily_history._build_report(
        config={"scope": "symbols", "start_date": "2024-05-28", "end_date": "2024-06-07"},
        totals={"ok": 1, "skip": 0, "empty": 1, "error": 1},
        results=[
            backfill_daily_history.BackfillResult("000001", "ok", rows=9, source="akshare.stock_zh_a_hist", adjusted_mode="qfq", data_quality="fresh:9"),
            backfill_daily_history.BackfillResult("000002", "empty", message="remote empty"),
            backfill_daily_history.BackfillResult("000003", "error", message="timeout"),
        ],
    )
    output = tmp_path / "report.json"

    backfill_daily_history._write_report(output, report)

    assert report["status"] == "partial_data"
    assert len(report["failed_symbols"]) == 2
    assert "正式回测仍必须通过" in report["notes"][1]
    assert output.read_text(encoding="utf-8").startswith("{")


def test_daily_backfill_marks_missing_limit_prices_as_partial_metadata() -> None:
    record = {
        "open": 10,
        "close": 10.2,
        "high": 10.5,
        "low": 9.8,
        "volume": 1000,
        "amount": 10000,
        "limit_up_price": 0,
        "limit_down_price": 0,
    }

    assert backfill_daily_history._daily_quality(record) == "partial_metadata"


def test_daily_backfill_fetch_filters_unavailable_ohlc_rows(monkeypatch) -> None:
    import pandas as pd

    class FakeAk:
        @staticmethod
        def stock_zh_a_hist(**_kwargs):
            return pd.DataFrame(
                [
                    {"date": "2024-05-28", "open": 0, "close": 10, "high": 0, "low": 0, "volume": 0, "amount": 0},
                    {"date": "2024-05-29", "open": 10, "close": 10.2, "high": 10.3, "low": 9.9, "volume": 1000, "amount": 10000},
                ]
            )

    monkeypatch.setattr(backfill_daily_history, "ak", FakeAk)
    monkeypatch.setattr(backfill_daily_history, "beijing_now", lambda: datetime(2026, 5, 29, 15, 31, 0))

    rows = backfill_daily_history._fetch_daily_rows(symbol="000001", start_date="2024-05-28", end_date="2024-05-29")

    assert [row.trade_date for row in rows] == ["2024-05-29"]
    assert rows[0].fetch_time == "2026-05-29T15:31:00"


def test_daily_backfill_coverage_requires_dense_window_and_lineage(monkeypatch) -> None:
    db = _session()
    for trade_date in ("2024-05-28", "2026-04-28"):
        db.add(
            DailyBarSnapshot(
                symbol="000001",
                market="CN",
                instrument_type="stock",
                trade_date=trade_date,
                open_price=10,
                close_price=10,
                high_price=10,
                low_price=10,
                volume=100,
                amount=1000,
                pct_chg=0,
                source="akshare.stock_zh_a_hist",
                fetch_time="2026-05-28T00:00:00",
                adjusted_mode="qfq",
                checksum="x" * 64,
                data_quality="fresh",
            )
        )
    db.commit()
    monkeypatch.setattr(backfill_daily_history, "SessionLocal", lambda: db)

    assert backfill_daily_history._coverage_is_complete(symbol="000001", start_date="2024-05-28", end_date="2026-04-28") is False

    db.add(
        DailyBarSnapshot(
            symbol="600000",
            market="CN",
            instrument_type="stock",
            trade_date="2026-04-28",
            open_price=10,
            close_price=10,
            high_price=10,
            low_price=10,
            volume=100,
            amount=1000,
            pct_chg=0,
            source="",
            fetch_time="",
            checksum="",
            data_quality="",
        )
    )
    db.commit()

    assert backfill_daily_history._coverage_is_complete(symbol="600000", start_date="2026-04-28", end_date="2026-04-28") is False


def test_clean_invalid_daily_bars_deletes_bad_ohlc_without_repairing_prices() -> None:
    db = _session()
    db.add(
        DailyBarSnapshot(
            symbol="688089",
            market="CN",
            instrument_type="stock",
            trade_date="2024-11-06",
            open_price=0,
            close_price=20.75,
            high_price=0,
            low_price=0,
            volume=0,
            amount=0,
            source="akshare.stock_zh_a_daily",
            data_quality="verified",
        )
    )
    db.add(
        DailyBarSnapshot(
            symbol="688089",
            market="CN",
            instrument_type="stock",
            trade_date="2024-11-07",
            open_price=20,
            close_price=20.75,
            high_price=21,
            low_price=19.8,
            volume=100,
            amount=2000,
            source="akshare.stock_zh_a_daily",
            data_quality="verified",
        )
    )
    db.commit()

    report = clean_invalid_daily_bars(db, start_date="2024-11-06", end_date="2024-11-07")
    db.commit()

    assert report["deleted_rows"] == 1
    assert db.query(DailyBarSnapshot).filter_by(symbol="688089").count() == 1
    assert str(db.query(DailyBarSnapshot).filter_by(symbol="688089").one().trade_date) == "2024-11-07"


def test_instrument_metadata_parser_keeps_missing_fields_unfilled() -> None:
    rows = backfill_instrument_metadata.parse_spot_records(
        [
            {"代码": "000001", "名称": "平安银行", "行业": "银行", "上市时间": "19910403"},
            {"f12": "000002", "f14": "万科A", "f100": "", "f26": "-"},
        ],
        source="test",
    )

    assert rows[0].sector_name == "银行"
    assert rows[0].listing_date == "1991-04-03"
    assert rows[1].sector_name == ""
    assert rows[1].listing_date == ""


def test_instrument_metadata_merges_exchange_listing_and_sw_industry_rows() -> None:
    listing = backfill_instrument_metadata.parse_spot_records(
        [{"A股代码": "000001", "A股简称": "平安银行", "A股上市日期": "1991-04-03", "所属行业": "J 金融业"}],
        source="sz",
    )
    sw = [backfill_instrument_metadata.MetadataRow(symbol="000001", name="", sector_name="货币金融服务")]

    merged = backfill_instrument_metadata.merge_metadata_rows(listing, sw)

    assert merged[0].name == "平安银行"
    assert merged[0].listing_date == "1991-04-03"
    assert merged[0].sector_name == "货币金融服务"


def test_instrument_metadata_resolves_sw_leaf_industry_names(monkeypatch) -> None:
    class FakeFrame:
        def __init__(self, records):
            self._records = records

        def to_dict(self, _kind):
            return self._records

    class FakeAk:
        @staticmethod
        def stock_industry_clf_hist_sw():
            return FakeFrame([{"symbol": "000001", "start_date": "2021-01-01", "industry_code": "480301", "update_time": "2026-01-01"}])

        @staticmethod
        def stock_industry_category_cninfo(symbol):
            return FakeFrame(
                [
                    {"类目编码": "48", "类目名称": "银行"},
                    {"类目编码": "4803", "类目名称": "股份制银行"},
                    {"类目编码": "480301", "类目名称": "股份制银行Ⅲ"},
                ]
            )

    monkeypatch.setattr(backfill_instrument_metadata, "ak", FakeAk)

    rows = backfill_instrument_metadata.fetch_sw_industry_rows([])

    assert rows[0].sector_name == "股份制银行"


def test_instrument_metadata_upsert_writes_industry_history_and_report_partial() -> None:
    db = _session()
    rows = [
        backfill_instrument_metadata.MetadataRow(
            symbol="000001",
            name="平安银行",
            sector_name="银行",
            listing_date="1991-04-03",
        )
    ]

    totals = backfill_instrument_metadata.upsert_metadata_rows(db, rows)
    db.commit()
    coverage = backfill_instrument_metadata.coverage_report(db)
    report = backfill_instrument_metadata.build_report(
        rows=[],
        provider_errors=[{"source": "eastmoney.clist", "message": "closed"}],
        totals=totals,
        coverage=coverage,
    )

    assert totals["created"] == 1
    assert coverage["sector_coverage_pct"] == 100.0
    history = db.query(InstrumentIndustryHistory).filter_by(symbol="000001").one()
    assert history.industry_name == "银行"
    assert str(history.trade_date) == "1991-04-03"
    assert report["status"] == "partial_data"
    assert "不会硬填" in report["notes"][0]


def _session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()
