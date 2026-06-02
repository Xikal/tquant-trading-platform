from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import key_levels
from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.base import Base
from app.models.entities import DailyBarSnapshot, Instrument, SystemSetting
from app.models.schema_defs.key_levels import KeyLevelDataQuality, KeyLevelDirection, KeyLevelResult
from app.services.key_levels.engine import AKeyLevelEngine
from app.services.key_levels.ma_levels import calculate_ma_levels
from app.services.key_levels.materialization import AKeyLevelMaterializationService, read_cached_key_level, write_cached_key_level
from app.services.key_levels.validation import KeyLevelValidationService
from app.services.shared.feature_flags import clear_feature_flag_cache


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
        if index == 20:
            low_price = close_base - 0.45
            high_price = close_base + 0.2
        elif index == 58:
            low_price = close_price - 0.1
            high_price = close_base + 2.2
        else:
            low_price = round(close_price - 0.15, 2)
            high_price = round(close_price + 0.18, 2)
        db.add(
            DailyBarSnapshot(
                symbol=symbol,
                market="CN",
                instrument_type=instrument_type,
                trade_date=trade_date,
                open_price=round(close_price - 0.05, 2),
                close_price=close_price,
                high_price=round(high_price, 2),
                low_price=round(low_price, 2),
                volume=1_000_000 + index * 10_000,
                amount=(1_000_000 + index * 10_000) * close_price,
                pct_chg=0.2,
                pre_close=round(close_price - 0.02, 2),
                adjusted_mode="qfq",
                data_quality="ok",
            )
        )
    db.commit()


def test_calculate_ma_levels_exposes_ma30() -> None:
    levels = calculate_ma_levels([float(item) for item in range(1, 61)])

    assert levels.ma5 == 58.0
    assert levels.ma30 == 45.5
    assert levels.ma60 == 30.5


def test_stock_key_levels_return_support_resistance_and_evidence() -> None:
    db = _session()
    _seed_symbol(db, "000001")

    result = AKeyLevelEngine(db).build_stock("000001", include_intraday=False)

    assert result.scope == "stock"
    assert result.support_price is not None
    assert result.resistance_price is not None
    assert result.support_strength > 0
    assert result.resistance_strength > 0
    assert result.ma30 is not None
    assert result.adjust_mode == "qfq"
    assert result.intraday_included is False
    assert result.data_quality == "ok"
    assert result.key_level_candidates
    assert all(candidate.evidence for candidate in result.key_level_candidates)
    assert all(0 <= candidate.strength_score <= 100 for candidate in result.key_level_candidates)
    assert "买入" not in result.explanation
    assert "卖出" not in result.explanation


def test_stock_key_levels_include_volume_profile_and_anchored_vwap_sources() -> None:
    db = _session()
    _seed_symbol(db, "000101")

    result = AKeyLevelEngine(db).build_stock("000101", include_intraday=False)
    level_types = {candidate.level_type for candidate in result.key_level_candidates}
    evidence_text = " ".join(" ".join(candidate.evidence) for candidate in result.key_level_candidates)

    assert "volume_profile" in level_types
    assert "Anchored VWAP" in evidence_text


def test_stock_key_levels_include_gap_and_limit_up_structure_sources() -> None:
    db = _session()
    _seed_symbol(db, "000105")
    rows = db.query(DailyBarSnapshot).filter(DailyBarSnapshot.symbol == "000105").order_by(DailyBarSnapshot.trade_date.asc()).all()
    rows[24].high_price = 10.0
    rows[25].low_price = 10.4
    rows[25].open_price = 10.5
    rows[25].close_price = 10.8
    rows[25].high_price = 10.9
    rows[25].pct_chg = 9.8
    rows[25].limit_up_price = 10.78
    db.commit()

    result = AKeyLevelEngine(db).build_stock("000105", include_intraday=False)
    evidence_text = " ".join(" ".join(candidate.evidence) for candidate in result.key_level_candidates)

    assert "向上缺口上沿" in evidence_text
    assert "涨停日" in evidence_text


def test_close_key_level_candidates_are_merged_with_score_clamp() -> None:
    db = _session()
    _seed_symbol(db, "000102")

    result = AKeyLevelEngine(db).build_stock("000102", include_intraday=False)
    unique_keys = {(candidate.direction, round(candidate.price, 2)) for candidate in result.key_level_candidates}

    assert len(unique_keys) == len(result.key_level_candidates)
    assert all(0 <= candidate.strength_score <= 100 for candidate in result.key_level_candidates)
    assert any(len(candidate.evidence) >= 2 for candidate in result.key_level_candidates)


def test_stock_key_levels_mark_insufficient_without_fake_score() -> None:
    db = _session()
    _seed_symbol(db, "000002", days=12)

    result = AKeyLevelEngine(db).build_stock("000002", include_intraday=False)

    assert result.data_quality == "insufficient"
    assert result.support_strength == 0
    assert result.resistance_strength == 0
    assert result.support_price is None
    assert result.resistance_price is None
    assert result.warnings


def test_key_level_validation_summary_is_machine_readable() -> None:
    db = _session()
    _seed_symbol(db, "000103", days=150)

    summary = KeyLevelValidationService(db).validate_symbol("000103", lookback_days=60, evaluation_days=30)
    payload = summary.as_payload()

    assert payload["symbol"] == "000103"
    assert payload["sample_count"] > 0
    assert "support_touch_count" in payload
    assert "support_effective_3d_count" in payload
    assert "support_failure_count" in payload
    assert payload["data_quality"] in {"ok", "research_only"}


def test_key_level_validation_uses_touch_pct_without_counting_deep_break_as_touch() -> None:
    db = _session()
    _seed_symbol(db, "000106", days=150)
    rows = db.query(DailyBarSnapshot).filter(DailyBarSnapshot.symbol == "000106").order_by(DailyBarSnapshot.trade_date.asc()).all()
    for row in rows[-30:]:
        row.low_price = 1.0
        row.close_price = 1.1
        row.high_price = 1.2
    db.commit()

    summary = KeyLevelValidationService(db).validate_symbol("000106", lookback_days=60, evaluation_days=20, touch_pct=0.3)

    assert summary.support_touch_count == 0


def test_key_level_validation_prefetches_history_instead_of_querying_per_sample() -> None:
    db = _session()
    _seed_symbol(db, "000107", days=150)
    query_count = 0
    original_execute = db.execute

    def counting_execute(*args, **kwargs):
        nonlocal query_count
        query_count += 1
        return original_execute(*args, **kwargs)

    db.execute = counting_execute  # type: ignore[method-assign]

    KeyLevelValidationService(db).validate_symbol("000107", lookback_days=60, evaluation_days=30)

    assert query_count <= 4


def test_key_level_validation_marks_short_history_insufficient() -> None:
    db = _session()
    _seed_symbol(db, "000104", days=12)

    summary = KeyLevelValidationService(db).validate_symbol("000104", lookback_days=60, evaluation_days=30)

    assert summary.data_quality == "insufficient"
    assert summary.sample_count == 0


def test_key_levels_do_not_use_rows_after_requested_trade_date() -> None:
    db = _session()
    _seed_symbol(db, "000003")
    before_future = AKeyLevelEngine(db).build_stock("000003", trade_date="2026-03-10", include_intraday=False)
    db.add(
        DailyBarSnapshot(
            symbol="000003",
            market="CN",
            instrument_type="stock",
            trade_date=date(2026, 4, 10),
            open_price=30,
            close_price=30,
            high_price=80,
            low_price=2,
            volume=9_999_999,
            amount=9_999_999 * 30,
            pct_chg=0,
            pre_close=30,
            adjusted_mode="qfq",
            data_quality="ok",
        )
    )
    db.commit()

    after_future = AKeyLevelEngine(db).build_stock("000003", trade_date="2026-03-10", include_intraday=False)

    assert after_future.support_price == before_future.support_price
    assert after_future.resistance_price == before_future.resistance_price
    assert after_future.as_of == "2026-03-10"


def test_market_and_sector_key_levels_share_unified_schema() -> None:
    db = _session()
    _seed_symbol(db, "000001", sector_name="银行", close_base=10)
    _seed_symbol(db, "000002", sector_name="银行", close_base=20)
    _seed_symbol(db, "000300", name="沪深300", instrument_type="index", sector_name="", close_base=3000)

    engine = AKeyLevelEngine(db)
    sector_result = engine.build_sector("银行", include_intraday=False)
    market_result = engine.build_market(include_intraday=False)

    assert sector_result.scope == "sector"
    assert sector_result.symbol == "银行"
    assert sector_result.support_price is not None
    assert market_result.scope == "market"
    assert market_result.support_price is not None
    assert sector_result.data_quality in {"ok", "research_only"}
    assert market_result.data_quality in {"ok", "research_only"}


def test_key_level_schema_has_versioned_machine_readable_invalidation() -> None:
    payload = KeyLevelResult(
        symbol="000001",
        scope="stock",
        trade_date="2026-06-02",
        latest_price=10.0,
        engine_version="akey-level-v1",
        as_of="2026-06-02",
        adjust_mode="qfq",
        intraday_included=False,
        support_price=9.8,
        support_zone_low=9.75,
        support_zone_high=9.86,
        support_distance_pct=-2.0,
        support_strength=80,
        support_level_type="platform_low",
        resistance_price=10.5,
        resistance_zone_low=10.42,
        resistance_zone_high=10.58,
        resistance_distance_pct=5.0,
        resistance_strength=72,
        resistance_level_type="volume_profile",
        ma5=9.95,
        ma10=9.9,
        ma20=9.88,
        ma30=9.86,
        ma60=9.5,
        close_to_ma5=0.5,
        close_to_ma10=1.0,
        close_to_ma20=1.2,
        close_to_ma30=1.4,
        close_to_ma60=5.3,
        trend_above_ma30=True,
        trend_above_ma60=True,
        key_level_candidates=[],
        data_quality="ok",
        explanation="接近支撑，仅用于观察。",
        warnings=[],
    )

    direction: KeyLevelDirection = "support"
    quality: KeyLevelDataQuality = "research_only"

    assert payload.engine_version == "akey-level-v1"
    assert payload.adjust_mode == "qfq"
    assert direction == "support"
    assert quality == "research_only"


def test_key_level_materialization_writes_cache_for_stock_sector_market() -> None:
    db = _session()
    _seed_symbol(db, "000001", sector_name="银行")
    _seed_symbol(db, "000002", sector_name="银行", close_base=20)
    _seed_symbol(db, "000300", name="沪深300", instrument_type="index", close_base=3000)

    summary = AKeyLevelMaterializationService(db).refresh(trade_date="2026-03-21", symbols=["000001"], sectors=["银行"])

    assert summary["ok"] is True
    assert summary["stock_count"] == 1
    assert summary["sector_count"] == 1
    assert summary["market_count"] == 1
    assert read_cached_key_level(db, scope="stock", key="000001", trade_date="2026-03-21") is not None
    assert read_cached_key_level(db, scope="sector", key="银行", trade_date="2026-03-21") is not None
    assert read_cached_key_level(db, scope="market", key="market", trade_date="2026-03-21") is not None


def test_key_level_materialization_default_covers_all_active_stocks_and_sectors() -> None:
    db = _session()
    for index in range(85):
        _seed_symbol(db, f"60{index:04d}", sector_name=f"行业{index % 25}", days=80)
    _seed_symbol(db, "000300", name="沪深300", instrument_type="index", sector_name="", close_base=3000)

    summary = AKeyLevelMaterializationService(db).refresh(trade_date="2026-03-21")

    assert summary["stock_count"] == 85
    assert summary["sector_count"] == 25
    assert read_cached_key_level(db, scope="stock", key="600084", trade_date="2026-03-21") is not None
    assert read_cached_key_level(db, scope="sector", key="行业24", trade_date="2026-03-21") is not None


def test_key_level_api_feature_flag_off_returns_blocked_research_status() -> None:
    db = _session()
    _seed_symbol(db, "000001", sector_name="银行")
    app = FastAPI()
    app.include_router(key_levels.router, prefix="/api")
    app.dependency_overrides[get_current_user] = _user
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)

    stock = client.get("/api/key-levels/stock/000001").json()

    assert stock["data_quality"] == "blocked"
    assert stock["support_price"] is None
    assert "功能开关关闭" in stock["warnings"][0]


def test_stock_api_degrades_when_market_or_sector_layer_missing() -> None:
    db = _session()
    _seed_symbol(db, "000001", sector_name="银行")
    db.add(SystemSetting(key="ff_a_key_level_engine_enabled", value="true"))
    stock_result = AKeyLevelEngine(db).build_stock("000001", trade_date="2026-03-21", include_intraday=False)
    original_strength = stock_result.support_strength
    write_cached_key_level(db, stock_result)
    db.commit()
    app = FastAPI()
    app.include_router(key_levels.router, prefix="/api")
    app.dependency_overrides[get_current_user] = _user
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)

    stock = client.get("/api/key-levels/stock/000001?trade_date=2026-03-21").json()

    assert stock["data_quality"] == "research_only"
    assert stock["support_strength"] < original_strength
    assert any("大盘关键位缺失" in item for item in stock["warnings"])
    assert any("板块关键位缺失" in item for item in stock["warnings"])


def test_key_level_api_returns_stock_sector_market_results() -> None:
    db = _session()
    _seed_symbol(db, "000001", sector_name="银行")
    _seed_symbol(db, "000002", sector_name="银行", close_base=20)
    _seed_symbol(db, "000300", name="沪深300", instrument_type="index", close_base=3000)
    db.add(SystemSetting(key="ff_a_key_level_engine_enabled", value="true"))
    AKeyLevelMaterializationService(db).refresh(trade_date="2026-03-21", symbols=["000001"], sectors=["银行"])
    db.commit()
    app = FastAPI()
    app.include_router(key_levels.router, prefix="/api")
    app.dependency_overrides[get_current_user] = _user
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)

    stock = client.get("/api/key-levels/stock/000001").json()
    sector = client.get("/api/key-levels/sector/银行").json()
    market = client.get("/api/key-levels/market").json()

    assert stock["scope"] == "stock"
    assert sector["scope"] == "sector"
    assert market["scope"] == "market"
    assert "ma30" in stock
    assert "key_level_candidates" in stock


def test_key_level_api_does_not_allow_request_time_refresh() -> None:
    db = _session()
    _seed_symbol(db, "000008", sector_name="银行")
    db.add(SystemSetting(key="ff_a_key_level_engine_enabled", value="true"))
    db.commit()
    app = FastAPI()
    app.include_router(key_levels.router, prefix="/api")
    app.dependency_overrides[get_current_user] = _user
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)

    response = client.get("/api/key-levels/stock/000008?refresh=true")

    assert response.status_code == 422
