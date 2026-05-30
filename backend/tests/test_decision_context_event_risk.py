from __future__ import annotations

from datetime import date, datetime, timedelta
from os import environ

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.models.base import Base
from app.models.entities import MarketEventCache
from app.services.decision_context.event_risk import (
    EventRiskInput,
    classify_event_risk,
    evaluate_event_risk_gate,
    refresh_event_risk,
)


def test_high_risk_reduction_blocks_only_when_production_flag_enabled() -> None:
    previous = environ.get("EVENT_RISK_PRODUCTION_BLOCK_ENABLED")
    environ["EVENT_RISK_PRODUCTION_BLOCK_ENABLED"] = "true"
    get_settings.cache_clear()
    try:
        result = evaluate_event_risk_gate(
            EventRiskInput(
                symbol="600000",
                trade_date=date(2026, 5, 31),
                events=[
                    {
                        "title": "控股股东拟大额减持",
                        "description": "计划减持股份比例较高，可能造成抛压。",
                        "source": "notice",
                        "event_time": "2026-05-31",
                    }
                ],
            )
        )
    finally:
        if previous is None:
            environ.pop("EVENT_RISK_PRODUCTION_BLOCK_ENABLED", None)
        else:
            environ["EVENT_RISK_PRODUCTION_BLOCK_ENABLED"] = previous
        get_settings.cache_clear()

    assert result.decision == "block"
    assert result.data_quality == "ok"
    assert any("减持" in reason for reason in result.reasons)


def test_high_risk_event_is_summary_only_when_production_flag_disabled() -> None:
    get_settings.cache_clear()
    result = evaluate_event_risk_gate(
        EventRiskInput(
            symbol="600000",
            trade_date=date(2026, 5, 31),
            events=[
                {
                    "title": "控股股东拟大额减持",
                    "description": "计划减持股份比例较高。",
                    "source": "notice",
                    "event_time": "2026-05-31",
                }
            ],
        )
    )

    assert result.decision == "research_only"
    assert result.production_blocked is False
    assert result.data_quality == "ok"
    assert "生产阻断关闭" in result.summary


def test_missing_event_source_is_missing_not_allow() -> None:
    result = evaluate_event_risk_gate(EventRiskInput(symbol="600000", trade_date=date(2026, 5, 31), events=[]))

    assert result.decision == "no_data"
    assert result.data_quality == "missing"
    assert result.production_blocked is False
    assert any("事件源" in reason for reason in result.reasons)


def test_medium_risk_event_reduces_and_warns_without_blocking() -> None:
    result = evaluate_event_risk_gate(
        EventRiskInput(
            symbol="600000",
            trade_date=date(2026, 5, 31),
            events=[
                {
                    "title": "交易所问询函",
                    "description": "重组事项仍有不确定性。",
                    "source": "notice",
                    "event_time": "2026-05-31",
                }
            ],
        )
    )

    assert result.decision == "reduce"
    assert result.production_blocked is False
    assert result.severity == "medium"
    assert any("降分" in reason or "告警" in reason for reason in result.reasons)


def test_classify_event_risk_uses_high_risk_keywords() -> None:
    result = classify_event_risk({"title": "收到监管处罚并涉及重大诉讼", "description": ""})

    assert result["severity"] == "high"
    assert "监管处罚" in result["risk_types"]
    assert "重大诉讼" in result["risk_types"]


def test_refresh_event_risk_reads_cache_and_marks_missing() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)

    with Session() as db:
        db.add(
            MarketEventCache(
                symbol="600000",
                title="问询函",
                risk_level="medium",
                description="交易所问询函",
                source="notice",
                event_time="2026-05-31",
            )
        )
        db.commit()
        result = refresh_event_risk(db, symbols=["600000", "600001"], trade_date=date(2026, 5, 31))

    assert result["ok"] is True
    assert result["items"][0]["symbol"] == "600000"
    assert result["items"][0]["severity"] == "medium"
    assert result["items"][1]["symbol"] == "600001"
    assert result["items"][1]["data_quality"] == "missing"


def test_refresh_event_risk_treats_stale_cache_as_missing_even_when_block_flag_enabled() -> None:
    previous = environ.get("EVENT_RISK_PRODUCTION_BLOCK_ENABLED")
    environ["EVENT_RISK_PRODUCTION_BLOCK_ENABLED"] = "true"
    get_settings.cache_clear()
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)

    try:
        with Session() as db:
            db.add(
                MarketEventCache(
                    symbol="600000",
                    title="控股股东拟大额减持",
                    risk_level="high",
                    description="大额减持可能造成抛压",
                    source="notice",
                    event_time="2026-04-01",
                    created_at=datetime.utcnow() - timedelta(days=30),
                )
            )
            db.commit()
            result = refresh_event_risk(db, symbols=["600000"], trade_date=date(2026, 5, 31))
    finally:
        if previous is None:
            environ.pop("EVENT_RISK_PRODUCTION_BLOCK_ENABLED", None)
        else:
            environ["EVENT_RISK_PRODUCTION_BLOCK_ENABLED"] = previous
        get_settings.cache_clear()

    item = result["items"][0]
    assert item["decision"] == "no_data"
    assert item["data_quality"] == "missing"
    assert item["production_blocked"] is False
    assert any("陈旧" in reason or "过期" in reason for reason in item["reasons"])
