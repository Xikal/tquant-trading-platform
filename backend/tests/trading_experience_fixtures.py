from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import trading_experience
from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.schema_defs.key_levels import KeyLevelCandidate, KeyLevelResult
from app.models.base import Base
from app.models.entities import DailyBarSnapshot, Instrument, MinuteBarSnapshot, PaperAccount, PaperPosition, PaperTrade
from app.services.key_levels.materialization import write_cached_key_level
from app.services.shared.feature_flags import clear_feature_flag_cache


def user_stub():
    return SimpleNamespace(id=1, username="tester", is_active=True, can_paper_trade=True, roles="")


def session_factory():
    clear_feature_flag_cache()
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def client_for(Session) -> TestClient:
    app = FastAPI()
    app.include_router(trading_experience.router, prefix="/api")
    app.dependency_overrides[get_current_user] = user_stub

    def override_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    return TestClient(app)


def seed_daily_bars(db, symbol: str = "600000", *, pct: float = 8.8, sector: str = "银行") -> None:
    db.add(Instrument(symbol=symbol, name="测试股票", instrument_type="stock", sector_name=sector, status="active"))
    start = date(2026, 5, 20)
    for index in range(8):
        trade_date = start + timedelta(days=index)
        row_pct = pct if index == 4 else (-3.5 if index == 5 else 0.8)
        close = 10 + index * 0.1
        db.add(
            DailyBarSnapshot(
                symbol=symbol,
                trade_date=trade_date,
                instrument_type="stock",
                open_price=close - 0.1,
                close_price=close,
                high_price=close + 0.2,
                low_price=close - 0.2,
                volume=1_000_000 + index * 200_000,
                amount=(1_000_000 + index * 200_000) * close,
                pct_chg=row_pct,
                pre_close=close - 0.1,
                limit_up_price=close if row_pct >= 9.5 else 0,
                data_quality="ok",
                adjusted_mode="qfq",
            )
        )
    db.commit()


def seed_paper(db, symbol: str = "600000", *, user_id: int | None = 1) -> PaperAccount:
    account = PaperAccount(
        user_id=user_id,
        name="测试账户",
        initial_cash=Decimal("100000"),
        cash_available=Decimal("90000"),
        total_assets=Decimal("100000"),
        status="active",
    )
    db.add(account)
    db.flush()
    db.add(
        PaperPosition(
            account_id=account.id,
            symbol=symbol,
            name="测试股票",
            quantity=1000,
            available_quantity=1000,
            cost_basis=Decimal("10.0000"),
            latest_price=Decimal("9.0000"),
            market_value=Decimal("9000"),
            unrealized_pnl_pct=Decimal("-10.0000"),
        )
    )
    db.add(
        PaperTrade(
            order_id=1,
            account_id=account.id,
            symbol=symbol,
            side="buy",
            price=Decimal("10"),
            quantity=1000,
            gross_amount=Decimal("10000"),
            net_amount=Decimal("10000"),
            trade_time=datetime.now() - timedelta(days=3),
        )
    )
    db.add(
        PaperTrade(
            order_id=2,
            account_id=account.id,
            symbol=symbol,
            side="sell",
            price=Decimal("10.5"),
            quantity=500,
            gross_amount=Decimal("5250"),
            net_amount=Decimal("5250"),
            trade_time=datetime.now() - timedelta(days=1),
        )
    )
    db.commit()
    return account


def seed_minutes(db, symbol: str = "600000", *, days: int = 20) -> None:
    start = date.today() - timedelta(days=days)
    for index in range(days):
        day = start + timedelta(days=index)
        db.add(
            MinuteBarSnapshot(
                symbol=symbol,
                trade_date=day,
                bar_period="1m",
                bar_timestamp=f"{day.isoformat()} 09:30:00",
                last_price=10,
                open_price=10,
                close_price=10,
                high_price=10,
                low_price=10,
                volume=1000,
                amount=10000,
                data_quality="ok",
            )
        )
    db.commit()


def seed_key_level(
    db,
    symbol: str = "600000",
    *,
    trade_date: str = "2026-05-24",
    latest_price: float = 10.05,
    support: float = 9.8,
    resistance: float = 10.2,
    data_quality: str = "ok",
) -> None:
    result = KeyLevelResult(
        symbol=symbol,
        name="测试股票",
        scope="stock",
        trade_date=trade_date,
        latest_price=latest_price,
        engine_version="akey-level-v1",
        as_of=f"{trade_date}T15:10:00",
        adjust_mode="qfq",
        intraday_included=False,
        support_price=support,
        support_zone_low=support * 0.99,
        support_zone_high=support * 1.01,
        support_distance_pct=(support - latest_price) / latest_price * 100.0,
        support_strength=82,
        support_level_type="platform_low",
        resistance_price=resistance,
        resistance_zone_low=resistance * 0.99,
        resistance_zone_high=resistance * 1.01,
        resistance_distance_pct=(resistance - latest_price) / latest_price * 100.0,
        resistance_strength=76,
        resistance_level_type="platform_high",
        ma5=latest_price,
        ma10=latest_price,
        ma20=latest_price,
        ma30=latest_price,
        ma60=latest_price,
        close_to_ma5=0.0,
        close_to_ma10=0.0,
        close_to_ma20=0.0,
        close_to_ma30=0.0,
        close_to_ma60=0.0,
        trend_above_ma30=latest_price >= support,
        trend_above_ma60=latest_price >= support,
        key_level_candidates=[
            KeyLevelCandidate(
                price=support,
                zone_low=support * 0.99,
                zone_high=support * 1.01,
                direction="support",
                level_type="platform_low",
                strength_score=82,
                evidence=["测试支撑平台"],
                invalid_condition=f"有效跌破 {support * 0.99:.2f}",
                invalidate_below=support * 0.99,
            ),
            KeyLevelCandidate(
                price=resistance,
                zone_low=resistance * 0.99,
                zone_high=resistance * 1.01,
                direction="resistance",
                level_type="platform_high",
                strength_score=76,
                evidence=["测试压力平台"],
                invalid_condition="放量越过压力后重新观察",
            ),
        ],
        data_quality=data_quality,  # type: ignore[arg-type]
        explanation="测试关键位，仅用于观察。",
        warnings=[],
    )
    write_cached_key_level(db, result)
    db.commit()


def seed_limit_up_backtest_bars(db, *, symbols: int = 6, events_per_symbol: int = 8, positive: bool = True) -> None:
    start = date(2024, 6, 1)
    total_days = 735
    for symbol_index in range(symbols):
        symbol = f"60{symbol_index:04d}"
        db.add(Instrument(symbol=symbol, name=f"回测{symbol_index}", instrument_type="stock", sector_name="测试", status="active"))
        close = 10.0 + symbol_index
        event_days = {20 + event * 70 + symbol_index for event in range(events_per_symbol)}
        for day_index in range(total_days):
            trade_date = start + timedelta(days=day_index)
            pct = 0.1
            volume = 1_000_000
            if day_index in event_days:
                pct = 9.8
                close *= 1.098
                volume = 3_000_000
            elif day_index - 3 in event_days:
                pct = -0.2
                close *= 0.998
                volume = 900_000
            elif day_index - 8 in event_days:
                pct = 3.0 if positive else -8.0
                close *= 1 + pct / 100
                volume = 1_100_000
            else:
                close *= 1.001 if positive else 0.999
            db.add(
                DailyBarSnapshot(
                    symbol=symbol,
                    trade_date=trade_date,
                    instrument_type="stock",
                    open_price=close * 0.99,
                    close_price=close,
                    high_price=close * 1.01,
                    low_price=close * 0.98,
                    volume=volume,
                    amount=volume * close,
                    pct_chg=pct,
                    pre_close=close / (1 + pct / 100) if pct else close,
                    limit_up_price=close if pct >= 9.5 else 0,
                    data_quality="ok",
                    adjusted_mode="qfq",
                )
            )
    db.commit()
