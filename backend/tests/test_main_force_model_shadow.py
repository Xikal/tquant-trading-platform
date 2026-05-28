from __future__ import annotations

import json

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.entities import DailyBarSnapshot, LowBuyResultSnapshot, LowBuyScanSnapshot, MarketModelObservation
from app.services.low_buy_materialization import warm_main_force_shadow_observations
from app.services.low_buy.main_force_model_schema import MAIN_FORCE_MODEL_OBSERVATION_KEY
from app.services.low_buy.main_force_model_shadow import (
    record_main_force_shadow,
    settle_main_force_shadow,
    summarize_main_force_shadow,
)
from backend.tests.main_force_model_test_helpers import main_force_candidate


def _db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()


def test_main_force_shadow_upserts_by_model_symbol_trade_date_and_action() -> None:
    db = _db()
    candidate = main_force_candidate()
    advice = _advice(score=68.0, confidence=0.68)

    record_main_force_shadow(db, candidate=candidate, advice=advice)
    record_main_force_shadow(db, candidate=candidate, advice=_advice(score=72.0, confidence=0.72))
    db.commit()

    rows = db.execute(select(MarketModelObservation)).scalars().all()
    assert len(rows) == 1
    assert rows[0].model_key == MAIN_FORCE_MODEL_OBSERVATION_KEY
    assert rows[0].trade_date == "2026-04-24"
    assert rows[0].signal_state == "buy_probe"
    assert rows[0].score == 72.0
    payload = json.loads(rows[0].payload_json)
    assert payload["model_advice"]["score"] == 72.0
    assert payload["fallback_reason"] is None


def test_main_force_shadow_summary_and_settle_include_outcomes() -> None:
    db = _db()
    candidate = main_force_candidate()
    record_main_force_shadow(db, candidate=candidate, advice=_advice())
    for idx, trade_date in enumerate(["2026-04-24", "2026-04-27", "2026-04-28", "2026-04-29", "2026-04-30"]):
        price = 11.7 + idx * 0.2
        db.add(
            DailyBarSnapshot(
                symbol="300001",
                market="CN",
                instrument_type="stock",
                trade_date=trade_date,
                open_price=price,
                close_price=price,
                high_price=price * 1.03,
                low_price=price * 0.99,
                volume=1_000_000,
                amount=120_000_000,
                pct_chg=1.0,
            )
        )
    db.commit()

    assert settle_main_force_shadow(db) == 1
    summary = summarize_main_force_shadow(db, lookback_days=3650)

    assert summary["model_key"] == MAIN_FORCE_MODEL_OBSERVATION_KEY
    assert summary["record_count"] == 1
    assert summary["settled_count"] == 1
    assert summary["success_rate_pct"] >= 0
    assert summary["promotion_ready"] is False
    assert summary["promotion_blockers"]


def test_main_force_shadow_warmup_runs_allowed_strategy_reference_path(monkeypatch) -> None:
    calls = []

    class DummySession:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def execute(self, _stmt):
            class Result:
                def scalar(self):
                    return len(calls)

            return Result()

        def commit(self):
            pass

        def rollback(self):
            pass

    class DummyRuntime:
        def _screen_sync(self, **kwargs):
            calls.append(kwargs)

            class Payload:
                latest_trade_date = "2026-04-24"
                matched_count = 3

            return Payload()

    class DummyScreener:
        def __init__(self):
            self._runtime = DummyRuntime()

    monkeypatch.setattr("app.core.database.SessionLocal", lambda: DummySession())
    monkeypatch.setattr("app.services.low_buy_screener.LowBuyScreenerService", DummyScreener)

    result = warm_main_force_shadow_observations(
        strategies=["volume_shrink", "first_board", "n_pattern_long_wash"],
        limit=200,
        scan_limit=900,
    )

    assert result["enabled"] is True
    assert result["strategies"] == ["n_pattern_long_wash", "volume_shrink"]
    assert len(calls) == 2
    assert all(call["bypass_cache"] is True for call in calls)
    assert all(call["record_shadow"] is True for call in calls)
    assert all(call["scan_limit"] == 480 for call in calls)
    assert all(call["limit"] == 80 for call in calls)


def test_main_force_shadow_warmup_prefers_materialized_candidates(monkeypatch) -> None:
    db = _db()
    candidate = main_force_candidate()
    db.add(
        LowBuyScanSnapshot(
            latest_trade_date="2026-04-24",
            strategy_key="volume_shrink",
            strategy_title="缩量回踩",
            as_of_date="2026-04-24",
            matched_count=1,
            filters_json=json.dumps({"market_state": "repair", "market_state_strength": 0.7}),
        )
    )
    db.add(
        LowBuyResultSnapshot(
            latest_trade_date="2026-04-24",
            strategy_key="volume_shrink",
            symbol=candidate.symbol,
            name=candidate.name,
            score=candidate.score,
            buy_signal_state=candidate.buy_signal_state,
            payload_json=candidate.model_dump_json(),
        )
    )
    for row in _history_rows():
        db.add(DailyBarSnapshot(**row))
    db.commit()

    class FailingRuntime:
        def _screen_sync(self, **_kwargs):
            raise AssertionError("reference screen path should not run when materialized candidates exist")

    class DummyScreener:
        def __init__(self):
            self._runtime = FailingRuntime()

    monkeypatch.setattr("app.core.database.SessionLocal", lambda: db)
    monkeypatch.setattr("app.services.low_buy_screener.LowBuyScreenerService", DummyScreener)

    result = warm_main_force_shadow_observations(strategies=["volume_shrink"], limit=10, scan_limit=80)

    rows = db.execute(select(MarketModelObservation)).scalars().all()
    assert result["ok"] is True
    assert result["records_added"] == 1
    assert result["refreshed"] == ["materialized:volume_shrink:2026-04-24:1"]
    assert len(rows) == 1
    assert rows[0].model_key == MAIN_FORCE_MODEL_OBSERVATION_KEY
    assert rows[0].symbol == "300001"
    assert rows[0].trade_date == "2026-04-24"


def _advice(*, score: float = 68.5, confidence: float = 0.685) -> dict:
    return {
        "model": "main-force-accumulation-washout-markup-v1",
        "stage": "washout",
        "stage_text": "洗盘确认",
        "action": "buy_probe",
        "action_text": "小仓试买",
        "score": score,
        "confidence": confidence,
        "buy_zone": [11.2, 11.9],
        "stop_loss": 10.8,
        "take_profit_plan": [{"level": "first", "price": 12.6, "action": "sell_30"}],
        "reasons": ["近 10 日出现适中回撤。"],
        "risk_flags": [],
        "feature_snapshot": {"as_of_date": "2026-04-24", "max_source_date": "2026-04-24"},
        "shadow_only": True,
        "production_effect": "readonly_shadow",
        "fallback_reason": None,
    }


def _history_rows() -> list[dict]:
    rows = []
    for idx, trade_date in enumerate(["2026-04-20", "2026-04-21", "2026-04-22", "2026-04-23", "2026-04-24"]):
        price = 11.0 + idx * 0.18
        rows.append(
            {
                "symbol": "300001",
                "market": "CN",
                "instrument_type": "stock",
                "trade_date": trade_date,
                "open_price": price * 0.99,
                "close_price": price,
                "high_price": price * 1.03,
                "low_price": price * 0.98,
                "volume": 1_000_000 + idx * 100_000,
                "amount": 120_000_000 + idx * 10_000_000,
                "pct_chg": 1.0,
            }
        )
    return rows
