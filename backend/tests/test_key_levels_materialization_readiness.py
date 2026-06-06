from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, inspect, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import create_engine

from app.api.routes import key_levels
from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.schema_compat import ensure_schema_compatibility
from app.models.base import Base
from app.models.entities import DailyBarSnapshot, Instrument, SystemSetting
from app.services import latest_data_close_refresh as close_refresh
from app.services.key_levels import materialization
from app.services.key_levels.engine import AKeyLevelEngine
from app.services.key_levels.materialization import (
    AKeyLevelMaterializationService,
    read_cached_key_level,
    write_cached_key_level,
)
from app.services.shared.feature_flags import clear_feature_flag_cache
from app.workers.runtime_worker import _execute_task


def _session():
    clear_feature_flag_cache()
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    return session_factory()


def _user():
    return SimpleNamespace(id=1, username="tester", is_active=True)


def _seed_symbol(
    db,
    symbol: str,
    *,
    name: str = "测试股票",
    instrument_type: str = "stock",
    sector_name: str = "银行",
    close_base: float = 10.0,
    days: int = 80,
) -> None:
    db.add(
        Instrument(
            symbol=symbol,
            name=name,
            instrument_type=instrument_type,
            sector_name=sector_name,
            status="active",
        )
    )
    start = date(2026, 1, 1)
    for index in range(days):
        trade_date = start + timedelta(days=index)
        close_price = round(close_base + index * 0.02, 2)
        db.add(
            DailyBarSnapshot(
                symbol=symbol,
                market="CN",
                instrument_type=instrument_type,
                trade_date=trade_date,
                open_price=round(close_price - 0.05, 2),
                close_price=close_price,
                high_price=round(close_price + 0.18, 2),
                low_price=round(close_price - 0.15, 2),
                volume=1_000_000 + index * 10_000,
                amount=(1_000_000 + index * 10_000) * close_price,
                pct_chg=0.2,
                pre_close=round(close_price - 0.02, 2),
                adjusted_mode="qfq",
                data_quality="ok",
            )
        )
    db.commit()


def _client(db) -> TestClient:
    app = FastAPI()
    app.include_router(key_levels.router, prefix="/api")
    app.dependency_overrides[get_current_user] = _user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app, raise_server_exceptions=False)


def test_after_close_enqueues_a_key_level_materialization_with_stable_idempotency_key(monkeypatch) -> None:
    class _FakeRepo:
        def __init__(self, _db) -> None:
            pass

        def stock_count_by_trade_date(self, _trade_date: str) -> int:
            return close_refresh.MIN_STOCK_DAILY_BARS

    payloads = []

    class _FakeQueue:
        def __init__(self, _db) -> None:
            pass

        def enqueue(self, payload):
            payloads.append(payload)
            return SimpleNamespace(id=len(payloads), status="queued")

    monkeypatch.setattr(close_refresh, "is_a_share_trading_day", lambda _date: True)
    monkeypatch.setattr(close_refresh, "expected_low_buy_trade_date", lambda _db: "2026-05-18")
    monkeypatch.setattr(close_refresh, "DailyHistoryRepository", _FakeRepo)
    monkeypatch.setattr(close_refresh, "RuntimeTaskQueue", _FakeQueue)
    monkeypatch.setattr(
        close_refresh,
        "daily_bar_freshness_status",
        lambda _db, _trade_date: {
            "daily_bar_count": close_refresh.MIN_STOCK_DAILY_BARS,
            "post_close_daily_bar_count": close_refresh.MIN_STOCK_DAILY_BARS,
            "daily_bar_freshness_status": "post_close_complete",
        },
    )
    monkeypatch.setattr(close_refresh, "latest_data_status", lambda _db, strategies: {"missing_strategies": []})
    monkeypatch.setattr(
        close_refresh,
        "publish_latest_trade_date_if_ready",
        lambda _db, strategies: {"status": "success", "published_trade_date": "2026-05-18"},
    )
    db = SimpleNamespace(committed=False, commit=lambda: setattr(db, "committed", True))

    result = close_refresh.enqueue_latest_data_close_refresh(
        db,
        now=datetime(2026, 5, 18, 15, 2),
        strategies=["volume_shrink"],
    )

    key_level_payloads = [item for item in payloads if item.task_type == "a_key_level_materialization_refresh"]
    assert result["a_key_level_materialization_task_status"] == "queued"
    assert len(key_level_payloads) == 1
    assert key_level_payloads[0].payload == {
        "trade_date": "2026-05-18",
        "reason": "after_close_latest_data",
    }
    assert key_level_payloads[0].idempotency_key == "a_key_level_materialization_refresh:2026-05-18"


def test_intraday_api_reads_cached_daily_levels_without_rebuilding_stock(monkeypatch) -> None:
    db = _session()
    _seed_symbol(db, "000001")
    db.add(SystemSetting(key="ff_a_key_level_engine_enabled", value="true"))
    daily = AKeyLevelEngine(db).build_stock("000001", trade_date="2026-03-21", include_intraday=False)
    write_cached_key_level(db, daily)
    db.commit()

    def forbidden_build_stock(self, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        raise AssertionError("intraday API must not rebuild daily stock levels")

    def fake_with_intraday(self, result, *, threshold_pct=0.3):  # noqa: ANN001
        return result.model_copy(update={"intraday_included": True})

    monkeypatch.setattr(AKeyLevelEngine, "build_stock", forbidden_build_stock)
    monkeypatch.setattr(AKeyLevelEngine, "with_intraday", fake_with_intraday)

    response = _client(db).get("/api/key-levels/intraday/000001")

    assert response.status_code == 200
    payload = response.json()
    assert payload["scope"] == "stock"
    assert payload["intraday_included"] is True


def test_key_level_cache_uses_snapshot_table_and_latest_precise_lookup() -> None:
    db = _session()
    _seed_symbol(db, "000001")
    old_result = AKeyLevelEngine(db).build_stock("000001", trade_date="2026-03-20", include_intraday=False)
    latest_result = AKeyLevelEngine(db).build_stock("000001", trade_date="2026-03-21", include_intraday=False)

    write_cached_key_level(db, old_result)
    write_cached_key_level(db, latest_result)
    write_cached_key_level(db, latest_result.model_copy(update={"latest_price": latest_result.latest_price + 1.0}))
    db.commit()

    snapshot_table = Base.metadata.tables.get("key_level_snapshots")
    assert snapshot_table is not None
    snapshot_count = db.execute(select(func.count()).select_from(snapshot_table)).scalar_one()
    system_cache_count = db.execute(
        select(func.count(SystemSetting.id)).where(SystemSetting.key.like("akey_level_cache:%"))
    ).scalar_one()

    assert snapshot_count == 2
    assert system_cache_count == 0
    latest = read_cached_key_level(db, scope="stock", key="000001")
    assert latest is not None
    assert latest.trade_date == "2026-03-21"
    assert latest.latest_price == latest_result.latest_price + 1.0


def test_key_level_cache_cleanup_removes_old_trade_dates() -> None:
    db = _session()
    _seed_symbol(db, "000001")
    for trade_date in ("2026-03-19", "2026-03-20", "2026-03-21"):
        write_cached_key_level(
            db,
            AKeyLevelEngine(db).build_stock("000001", trade_date=trade_date, include_intraday=False),
        )
    db.commit()

    assert hasattr(materialization, "cleanup_old_key_level_snapshots")
    removed = materialization.cleanup_old_key_level_snapshots(db, keep_trade_dates=1)
    db.commit()

    assert removed == 2
    assert read_cached_key_level(db, scope="stock", key="000001", trade_date="2026-03-19") is None
    assert read_cached_key_level(db, scope="stock", key="000001", trade_date="2026-03-21") is not None


def test_key_level_materialization_batches_commits_and_is_idempotent() -> None:
    db = _session()
    for index in range(5):
        _seed_symbol(db, f"00000{index}", sector_name=f"行业{index % 2}", close_base=10 + index)
    _seed_symbol(db, "000300", name="沪深300", instrument_type="index", sector_name="", close_base=3000)

    original_commit = db.commit
    commit_count = 0

    def counted_commit():
        nonlocal commit_count
        commit_count += 1
        original_commit()

    db.commit = counted_commit  # type: ignore[method-assign]
    summary = AKeyLevelMaterializationService(db).refresh(trade_date="2026-03-21", batch_size=2)
    first_count = db.execute(select(func.count()).select_from(Base.metadata.tables["key_level_snapshots"])).scalar_one()
    AKeyLevelMaterializationService(db).refresh(trade_date="2026-03-21", batch_size=2)
    second_count = db.execute(select(func.count()).select_from(Base.metadata.tables["key_level_snapshots"])).scalar_one()

    assert summary["stock_count"] == 5
    assert summary["sector_count"] == 2
    assert commit_count >= 4
    assert first_count == 8
    assert second_count == first_count


def test_key_level_materialization_recovers_after_mid_batch_failure(monkeypatch) -> None:
    db = _session()
    for index in range(3):
        _seed_symbol(db, f"00000{index}", sector_name="银行", close_base=10 + index)
    _seed_symbol(db, "000300", name="沪深300", instrument_type="index", sector_name="", close_base=3000)
    original_load_rows = AKeyLevelEngine._load_rows
    failed = False

    def flaky_load_rows(self, symbol, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        nonlocal failed
        if symbol == "000001" and not failed:
            failed = True
            raise RuntimeError("temporary history read failure")
        return original_load_rows(self, symbol, *args, **kwargs)

    monkeypatch.setattr(AKeyLevelEngine, "_load_rows", flaky_load_rows)

    with pytest.raises(RuntimeError):
        AKeyLevelMaterializationService(db).refresh(
            trade_date="2026-03-21",
            symbols=["000000", "000001", "000002"],
            sectors=[],
            batch_size=1,
        )

    assert read_cached_key_level(db, scope="stock", key="000000", trade_date="2026-03-21") is not None
    assert read_cached_key_level(db, scope="stock", key="000001", trade_date="2026-03-21") is None

    summary = AKeyLevelMaterializationService(db).refresh(
        trade_date="2026-03-21",
        symbols=["000000", "000001", "000002"],
        sectors=[],
        batch_size=1,
    )

    assert summary["stock_count"] == 3
    assert read_cached_key_level(db, scope="stock", key="000001", trade_date="2026-03-21") is not None


def test_key_level_materialization_reuses_stock_history_for_sector_build(monkeypatch) -> None:
    db = _session()
    _seed_symbol(db, "000001", sector_name="银行", close_base=10)
    _seed_symbol(db, "000002", sector_name="银行", close_base=20)
    _seed_symbol(db, "000300", name="沪深300", instrument_type="index", sector_name="", close_base=3000)
    original_load_rows = AKeyLevelEngine._load_rows
    calls: list[str] = []

    def counting_load_rows(self, symbol, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        calls.append(str(symbol))
        return original_load_rows(self, symbol, *args, **kwargs)

    monkeypatch.setattr(AKeyLevelEngine, "_load_rows", counting_load_rows)

    AKeyLevelMaterializationService(db).refresh(
        trade_date="2026-03-21",
        symbols=["000001", "000002"],
        sectors=["银行"],
        batch_size=10,
    )

    assert calls.count("000001") == 1
    assert calls.count("000002") == 1
    assert calls.count("000300") == 1


def test_runtime_worker_materialization_task_defaults_to_full_coverage() -> None:
    db = _session()
    _seed_symbol(db, "000001", sector_name="银行", close_base=10)
    _seed_symbol(db, "000002", sector_name="银行", close_base=20)
    _seed_symbol(db, "000300", name="沪深300", instrument_type="index", sector_name="", close_base=3000)

    result = _execute_task("a_key_level_materialization_refresh", {"trade_date": "2026-03-21"}, db)

    assert result["stock_count"] == 2
    assert result["sector_count"] == 1
    assert read_cached_key_level(db, scope="stock", key="000002", trade_date="2026-03-21") is not None


def test_schema_compatibility_repair_creates_key_level_snapshot_table() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SystemSetting.__table__.create(bind=engine)

    ensure_schema_compatibility(engine)

    assert "key_level_snapshots" in inspect(engine).get_table_names()


def test_key_level_snapshot_table_has_formal_alembic_migration() -> None:
    table = Base.metadata.tables.get("key_level_snapshots")
    assert table is not None

    migration_path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "20260603_0001_key_level_snapshots.py"
    )
    migration_source = migration_path.read_text(encoding="utf-8")

    assert 'op.create_table(\n        "key_level_snapshots"' in migration_source
    for column_name in table.columns.keys():
        assert f'"{column_name}"' in migration_source
    assert "uq_key_level_snapshot_scope_key_day_version" in migration_source
    assert "ix_key_level_snapshots_latest" in migration_source
    assert "ix_key_level_snapshots_symbol_day" in migration_source
