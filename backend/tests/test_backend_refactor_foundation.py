from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy import Date, Numeric, create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.config import AppSettings
from app.models.base import Base
from app.models.entities import (
    DailyBarSnapshot,
    Instrument,
    MarketHourlySnapshotHistory,
    MarketPulseEvent,
    MinuteBarSnapshot,
    PaperAccount,
    PaperPosition,
    PaperPositionLot,
)
from app.models.schemas import KlineBar, QuoteSnapshot
from app.services.finance import rust_math
from app.services.low_buy import go_scan_worker
from app.services.market import go_read_client
from app.services.market_data import MarketDataService
from app.services.market.pulse_history import (
    list_hourly_snapshot_history,
    list_market_pulse_events,
    record_hourly_snapshot_history,
)
from app.services.market.minute_bar_store import MinuteBarSnapshotStore, parse_minute_trade_date
from app.services.paper.position import PaperPositionService


def test_backend_refactor_settings_expose_pool_and_bff_cache_controls() -> None:
    settings = AppSettings(
        database_url="mysql+pymysql://user:pass@localhost/db",
        auth_secret_key="x" * 64,
        tquant_settings_encryption_key="y" * 64,
        db_pool_size=5,
        db_max_overflow=7,
        db_pool_timeout=11,
        db_pool_recycle=120,
        bff_workspace_cache_enabled=True,
        bff_monitor_cache_ttl_seconds=9,
    )

    assert settings.db_pool_size == 5
    assert settings.db_max_overflow == 7
    assert settings.db_pool_timeout == 11
    assert settings.db_pool_recycle == 120
    assert settings.bff_workspace_cache_enabled is True
    assert settings.bff_monitor_cache_ttl_seconds == 9
    assert settings.tquant_bff_gateway_url == ""
    assert settings.tquant_bff_shadow_enabled is False
    assert settings.tquant_market_read_service_url == ""
    assert settings.tquant_go_scan_worker_url == ""
    assert settings.tquant_go_scan_enabled is True
    assert settings.rust_finance_math_enabled is True


def test_main_force_model_defaults_are_safe() -> None:
    settings = AppSettings(
        auth_secret_key="x" * 64,
        tquant_settings_encryption_key="y" * 64,
    )

    assert settings.main_force_model_enabled is True
    assert settings.main_force_model_shadow_enabled is True
    assert settings.main_force_model_display_enabled is True
    assert settings.main_force_model_ranking_enabled is False
    assert settings.main_force_model_paper_display_enabled is True
    assert settings.main_force_model_paper_suggestion_enabled is False
    assert settings.main_force_model_max_rank_bonus <= 4.0


def test_daily_bar_snapshot_uses_date_and_numeric_ohlcv_types() -> None:
    columns = DailyBarSnapshot.__table__.c

    assert isinstance(columns.trade_date.type.impl, Date)
    for name in ("open_price", "close_price", "high_price", "low_price", "volume", "amount"):
        assert isinstance(columns[name].type, Numeric)


def test_minute_bar_snapshot_has_trade_date_partition_key() -> None:
    columns = MinuteBarSnapshot.__table__.c

    assert isinstance(columns.trade_date.type.impl, Date)


def test_minute_bar_store_persists_trade_date_for_timeseries_queries() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)
    quote = QuoteSnapshot(
        symbol="510300",
        name="沪深300ETF",
        market="SH",
        instrument_type="etf",
        last_price=3.5,
        change_pct=0.8,
        change_amount=0.03,
        open_price=3.48,
        high_price=3.53,
        low_price=3.47,
        prev_close=3.47,
        volume=2200,
        amount=7724,
        timestamp="2026-05-24 10:31:00",
    )
    bars = [
        KlineBar(timestamp="2026-05-24 10:30", open=3.48, close=3.5, high=3.51, low=3.47, volume=1000, amount=3500),
        KlineBar(timestamp="2026-05-24 10:31", open=3.5, close=3.52, high=3.53, low=3.49, volume=1200, amount=4224),
    ]

    with Session() as db:
        persisted = MinuteBarSnapshotStore(db).persist(quote, bars)
        rows = MinuteBarSnapshotStore(db).list_bars(
            symbol="510300",
            trade_date=date(2026, 5, 24),
            limit=10,
        )

    assert persisted == 2
    assert [row.bar_timestamp for row in rows] == ["2026-05-24 10:31", "2026-05-24 10:30"]
    assert rows[0].trade_date == date(2026, 5, 24)
    assert parse_minute_trade_date("202605241031") == date(2026, 5, 24)


def test_paper_positions_eager_load_lots_without_n_plus_one() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)
    query_count = 0

    @event.listens_for(engine, "before_cursor_execute")
    def _count_queries(*args, **kwargs):
        nonlocal query_count
        query_count += 1

    with Session() as db:
        account = PaperAccount(name="test", initial_cash=Decimal("100000.00"), cash_available=Decimal("100000.00"))
        db.add(account)
        db.flush()
        for index in range(25):
            symbol = f"600{index:03d}"
            position = PaperPosition(
                account_id=account.id,
                symbol=symbol,
                name=symbol,
                quantity=100,
                available_quantity=100,
                cost_basis=Decimal("10.0000"),
            )
            db.add(position)
            db.flush()
            db.add(
                PaperPositionLot(
                    account_id=account.id,
                    position_id=position.id,
                    symbol=symbol,
                    quantity=100,
                    remaining=100,
                    available_date=date(2026, 5, 20),
                    cost_price=Decimal("10.0000"),
                )
            )
        db.commit()

    query_count = 0
    with Session() as db:
        rows = PaperPositionService(db).get_positions(1)
        assert len(rows) == 25
        assert sum(len(row.lots) for row in rows) == 25

    assert query_count <= 6


def test_rust_math_can_be_disabled_by_config(monkeypatch) -> None:
    monkeypatch.setattr(rust_math, "get_settings", lambda: SimpleNamespace(rust_finance_math_enabled=False))

    assert rust_math.rust_available() is False
    assert rust_math.rust_max_drawdown([100.0, 90.0, 110.0]) is None
    assert rust_math.rust_rolling_mean([1.0, 2.0, 3.0], 2) is None
    assert rust_math.rust_atr_wilder([1.0], [1.0], [1.0], 14) is None
    assert rust_math.rust_rsi_wilder([1.0, 2.0, 3.0], 2) is None
    assert rust_math.rust_vwap([1.0], [10.0]) is None
    assert rust_math.rust_rank_ic([1.0, 2.0], [2.0, 1.0]) is None


def test_go_market_read_client_is_disabled_without_url(monkeypatch) -> None:
    called = False

    def fake_remote(*args, **kwargs):
        nonlocal called
        called = True
        return {}

    monkeypatch.setattr(go_read_client, "remote_bff_get", fake_remote)
    monkeypatch.setattr(go_read_client, "get_settings", lambda: SimpleNamespace(tquant_market_read_service_url=""))

    assert go_read_client.load_go_market_read_quotes(["000001"]) == {}
    assert called is False


def test_go_market_read_client_parses_quote_payload(monkeypatch) -> None:
    monkeypatch.setattr(
        go_read_client,
        "get_settings",
        lambda: SimpleNamespace(tquant_market_read_service_url="http://go-market-read-service:8092"),
    )
    monkeypatch.setattr(
        go_read_client,
        "remote_bff_get",
        lambda *args, **kwargs: {
            "items": [
                {
                    "data_quality": "fresh",
                    "quote": {
                        "symbol": "000001",
                        "name": "平安银行",
                        "market": "SZ",
                        "instrument_type": "stock",
                        "last_price": 10.1,
                        "change_pct": 1.2,
                        "change_amount": 0.12,
                        "open_price": 10.0,
                        "high_price": 10.2,
                        "low_price": 9.9,
                        "prev_close": 9.98,
                        "volume": 1000,
                        "amount": 10100,
                        "timestamp": "2026-05-23 10:00:00",
                    },
                }
            ]
        },
    )

    result = go_read_client.load_go_market_read_quotes(["000001"])

    assert result["000001"].last_price == 10.1
    assert result["000001"].data_source == "go_market_read_service"


def test_go_market_read_client_parses_intraday_latest_payload(monkeypatch) -> None:
    monkeypatch.setattr(
        go_read_client,
        "get_settings",
        lambda: SimpleNamespace(tquant_market_read_service_url="http://go-market-read-service:8092"),
    )
    monkeypatch.setattr(
        go_read_client,
        "remote_bff_get",
        lambda *args, **kwargs: {
            "items": [
                {
                    "symbol": "000001",
                    "data_quality": "fresh",
                    "latest": {
                        "symbol": "000001",
                        "name": "平安银行",
                        "market": "SZ",
                        "instrument_type": "stock",
                        "last_price": 10.2,
                        "change_pct": 1.4,
                        "change_amount": 0.14,
                        "open_price": 10.0,
                        "high_price": 10.3,
                        "low_price": 9.9,
                        "prev_close": 10.06,
                        "volume": 1000,
                        "amount": 10200,
                        "timestamp": "2026-05-25 10:00:00",
                    },
                }
            ]
        },
    )

    result = go_read_client.load_go_intraday_latest(["000001"])

    assert result["000001"].last_price == 10.2
    assert result["000001"].data_source == "go_market_read_service"


def test_go_market_read_client_preserves_stale_quality(monkeypatch) -> None:
    monkeypatch.setattr(
        go_read_client,
        "get_settings",
        lambda: SimpleNamespace(tquant_market_read_service_url="http://go-market-read-service:8092"),
    )
    monkeypatch.setattr(
        go_read_client,
        "remote_bff_get",
        lambda *args, **kwargs: {
            "items": [
                {
                    "symbol": "000001",
                    "data_quality": "stale",
                    "latest": {
                        "symbol": "000001",
                        "name": "平安银行",
                        "market": "SZ",
                        "instrument_type": "stock",
                        "last_price": 10.2,
                        "change_pct": 1.4,
                        "change_amount": 0.14,
                        "open_price": 10.0,
                        "high_price": 10.3,
                        "low_price": 9.9,
                        "prev_close": 10.06,
                        "volume": 1000,
                        "amount": 10200,
                        "timestamp": "2026-05-25 10:00:00",
                    },
                }
            ]
        },
    )

    result = go_read_client.load_go_intraday_latest(["000001"])

    assert result["000001"].data_quality == "stale"
    assert result["000001"].source_quality == "stale"
    assert result["000001"].is_stale is True


def test_market_pulse_models_keep_defaults_in_python_only() -> None:
    hourly_columns = MarketHourlySnapshotHistory.__table__.c
    pulse_columns = MarketPulseEvent.__table__.c

    assert hourly_columns.data_quality.default.arg == "fresh"
    assert hourly_columns.snapshot_count.default.arg == 0
    assert hourly_columns.market_strength_score.default.arg == 0.0
    assert hourly_columns.payload_json.default.arg == "{}"
    assert hourly_columns.payload_json.server_default is None

    assert pulse_columns.pulse_level.default.arg == "unknown"
    assert pulse_columns.data_quality.default.arg == "unavailable"
    assert pulse_columns.pulse_text.default.arg == ""
    assert pulse_columns.suggested_action.default.arg == ""
    assert pulse_columns.payload_json.default.arg == "{}"
    assert pulse_columns.payload_json.server_default is None


def test_market_data_get_quote_prefers_go_intraday_latest(monkeypatch) -> None:
    quote = QuoteSnapshot(
        symbol="000001",
        name="平安银行",
        market="SZ",
        instrument_type="stock",
        last_price=10.2,
        change_pct=1.4,
        change_amount=0.14,
        open_price=10.0,
        high_price=10.3,
        low_price=9.9,
        prev_close=10.06,
        volume=1000,
        amount=10200,
        timestamp="2026-05-25 10:00:00",
        data_source="go_market_read_service",
    )
    called_provider = False

    def fail_provider(*_args, **_kwargs):
        nonlocal called_provider
        called_provider = True
        raise AssertionError("provider should not be called when go latest hits")

    service = MarketDataService()
    service._quote_cache.clear()
    monkeypatch.setattr("app.services.market.quotes.read_local_quote_snapshot", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("app.services.market.quotes.load_go_intraday_latest", lambda symbols: {"000001": quote})
    monkeypatch.setattr(service, "_market_provider_router_enabled", lambda: True)
    monkeypatch.setattr(service.provider_router, "fetch_quote", fail_provider)

    result = service.get_quote("000001")

    assert result.last_price == 10.2
    assert result.data_source == "go_market_read_service"
    assert called_provider is False


def test_go_market_read_client_parses_key_levels_payload(monkeypatch) -> None:
    calls = []

    def fake_remote(base_url, path, *, params=None, **kwargs):
        calls.append((base_url, path, params))
        return {
            "symbol": "000001",
            "name": "平安银行",
            "updated_at": "2026-05-25T10:00:00+08:00",
            "latest_price": 10.2,
            "vwap": 10.1,
            "entry_zone_low": 9.8,
            "entry_zone_high": 10.3,
            "alert_threshold_pct": 0.3,
            "alert_triggered": True,
            "alert_text": "000001 接近分时均价 VWAP",
            "levels": [
                {
                    "level_type": "vwap",
                    "level_text": "分时均价 VWAP",
                    "price": 10.1,
                    "distance_pct": 0.99,
                    "alert": False,
                }
            ],
            "data_quality_text": "Go key levels",
        }

    monkeypatch.setattr(
        go_read_client,
        "get_settings",
        lambda: SimpleNamespace(tquant_market_read_service_url="http://go-market-read-service:8092"),
    )
    monkeypatch.setattr(go_read_client, "remote_bff_get", fake_remote)

    response = go_read_client.load_go_intraday_key_levels(
        "000001",
        entry_zone_low=9.8,
        entry_zone_high=10.3,
        threshold_pct=0.3,
    )

    assert response is not None
    assert response.symbol == "000001"
    assert response.latest_price == 10.2
    assert response.entry_zone_low == 9.8
    assert response.entry_zone_high == 10.3
    assert response.levels[0].level_type == "vwap"
    assert calls[0][1] == "/api/market-read/v1/intraday-key-levels"
    assert calls[0][2]["entry_zone_low"] == 9.8
    assert calls[0][2]["entry_zone_high"] == 10.3


def test_go_market_read_client_parses_sector_strength_payload(monkeypatch) -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)
    calls = []

    def fake_remote(base_url, path, *, json_body=None, **kwargs):
        calls.append((base_url, path, json_body))
        return {
            "data_quality": "fresh",
            "sectors": [
                {
                    "sector": "银行",
                    "leaders": [
                        {
                            "symbol": "000001",
                            "name": "平安银行",
                            "last_price": 10.2,
                            "change_pct": 1.4,
                            "sector_median_change": 0.5,
                            "volume_ratio": 1.3,
                            "turnover_rate": 0.8,
                            "leader_score": 15.3,
                            "data_quality": "fresh",
                        }
                    ],
                }
            ],
        }

    monkeypatch.setattr(
        go_read_client,
        "get_settings",
        lambda: SimpleNamespace(tquant_market_read_service_url="http://go-market-read-service:8092"),
    )
    monkeypatch.setattr(go_read_client, "remote_bff_post", fake_remote)

    with Session() as db:
        db.add(Instrument(symbol="000001", name="平安银行", market="SZ", instrument_type="stock", sector_name="银行"))
        db.add(
            DailyBarSnapshot(
                symbol="000001",
                trade_date=date(2026, 5, 25),
                instrument_type="stock",
                open_price=Decimal("10.0"),
                close_price=Decimal("10.2"),
                high_price=Decimal("10.3"),
                low_price=Decimal("9.9"),
                volume=Decimal("1000"),
                amount=Decimal("10200"),
                pct_chg=Decimal("1.4"),
            )
        )
        db.commit()
        response = go_read_client.load_go_sector_relative_strength(
            db,
            hot_sectors=["银行"],
            sector_limit=1,
            per_sector_limit=5,
            trade_date="2026-05-25",
        )

    assert response is not None
    assert response.items[0].symbol == "000001"
    assert "Go market-read-service" in response.notes[0]
    assert calls[0][1] == "/api/market-read/v1/sector-relative-strength"
    assert calls[0][2]["sectors"][0]["sector"] == "银行"


def test_go_scan_worker_is_disabled_without_config(monkeypatch) -> None:
    called = False

    def fake_remote(*args, **kwargs):
        nonlocal called
        called = True
        return {}

    monkeypatch.setattr(go_scan_worker, "remote_bff_get", fake_remote)
    monkeypatch.setattr(
        go_scan_worker,
        "get_settings",
        lambda: SimpleNamespace(tquant_go_scan_worker_url="", tquant_go_scan_enabled=True),
    )

    result = go_scan_worker.run_go_scan_worker(strategies=["first_board"], scan_limit=12, limit=5, reason="test")

    assert result["enabled"] is False
    assert result["fallback_reason"] == "go_scan_worker_disabled"
    assert called is False


def test_go_scan_worker_triggers_production_run(monkeypatch) -> None:
    calls = []

    def fake_remote(base_url, path, *, params=None, **kwargs):
        calls.append((base_url, path, params))
        return {"ok": True, "refreshed": ["first_board:2026-05-25"]}

    monkeypatch.setattr(go_scan_worker, "remote_bff_get", fake_remote)
    monkeypatch.setattr(
        go_scan_worker,
        "get_settings",
        lambda: SimpleNamespace(
            tquant_go_scan_worker_url="http://go-scan-worker:8093",
            tquant_go_scan_enabled=True,
        ),
    )

    result = go_scan_worker.run_go_scan_worker(
        strategies=["volume_shrink", "first_board", "first_board"],
        scan_limit=72,
        limit=12,
        reason="test",
    )

    assert result["ok"] is True
    assert result["enabled"] is True
    assert result["fallback_reason"] == ""
    assert calls[0][2]["strategies"] == "first_board,volume_shrink"
    assert calls[0][2]["scan_limit"] == 72
    assert calls[0][2]["limit"] == 12
    assert calls[0][0] == "http://go-scan-worker:8093"
    assert calls[0][1] == "/api/scan-worker/v1/run"


def test_market_pulse_history_records_hourly_snapshot_upsert() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)

    with Session() as db:
        payload = {
            "ok": True,
            "updated_at": "2026-05-25 10:30:00",
            "snapshot_count": 5200,
            "market_strength_score": 21.5,
            "data_quality": "fresh",
        }
        record_hourly_snapshot_history(db, payload, bucket="202605251030")
        record_hourly_snapshot_history(db, {**payload, "snapshot_count": 5201}, bucket="202605251030")
        db.commit()
        rows = list_hourly_snapshot_history(db, trade_date="2026-05-25")
        raw_count = db.query(MarketHourlySnapshotHistory).count()

    assert raw_count == 1
    assert rows[0].snapshot_count == 5201
    assert rows[0].payload["market_strength_score"] == 21.5


def test_market_pulse_history_keeps_existing_snapshot_when_empty_retry_fails() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)

    with Session() as db:
        payload = {
            "ok": True,
            "updated_at": "2026-05-25 15:00:00",
            "snapshot_count": 5192,
            "market_strength_score": -35.9,
            "data_quality": "fresh",
        }
        record_hourly_snapshot_history(db, payload, bucket="202605251500")
        record_hourly_snapshot_history(
            db,
            {
                "ok": False,
                "updated_at": "2026-05-25 15:04:00",
                "snapshot_count": 0,
                "market_strength_score": 0.0,
                "data_quality": "unavailable",
            },
            bucket="202605251500",
        )
        db.commit()
        rows = list_hourly_snapshot_history(db, trade_date="2026-05-25")

    assert len(rows) == 1
    assert rows[0].data_quality == "fresh"
    assert rows[0].snapshot_count == 5192


def test_market_pulse_history_lists_pulse_events() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)

    with Session() as db:
        db.add(
            MarketPulseEvent(
                trade_date="2026-05-25",
                pulse_level="repair",
                data_quality="partial",
                pulse_text="市场修复",
                suggested_action="小仓确认",
                payload_json='{"pulse_level":"repair"}',
            )
        )
        db.commit()
        rows = list_market_pulse_events(db, trade_date="2026-05-25")

    assert rows[0].pulse_level == "repair"
    assert rows[0].payload["pulse_level"] == "repair"
