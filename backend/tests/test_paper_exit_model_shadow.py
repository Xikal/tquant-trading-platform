from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.entities import MarketModelObservation
from app.services.paper.exit_model_dataset import build_exit_model_dataset, synthetic_exit_model_records
from app.services.paper.exit_model_schema import EXIT_MODEL_OBSERVATION_KEY, ExitModelShadowRecord
from app.services.paper.exit_model_shadow import latest_exit_model_shadow_records, record_exit_model_shadow, summarize_exit_model_shadow


def _db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()


def _record(*, as_of: str = "2026-05-20T10:30:00", confidence: float = 0.8) -> ExitModelShadowRecord:
    return ExitModelShadowRecord(
        account_id=1,
        position_id=11,
        symbol="600000",
        name="浦发银行",
        strategy_key="first_board",
        as_of=as_of,
        rule_action="hold",
        rule_reason="规则持有",
        rule_sell_ratio=0.0,
        model_action="sell_50",
        model_confidence=confidence,
        model_reason=["pullback_risk_high"],
        model_version="exit-model-v1",
        fallback_reason=None,
        feature_snapshot={
            "expected_return_next": -0.5,
            "market_state": "weak",
            "feature_values": {
                "pnl_pct": 6.0,
                "max_profit_pct": 9.0,
                "pullback_from_high_pct": 3.0,
                "hold_days": 2.0,
                "available_ratio": 1.0,
                "position_pct": 8.0,
                "vwap_deviation_pct": -1.0,
                "rsi": 42.0,
                "atr_pct": 1.8,
                "high_pullback_ratio": 0.5,
                "volume_release_ratio": 0.7,
                "market_strength": 0.2,
                "sector_strength": 0.3,
                "rule_sell_ratio": 0.0,
            },
        },
        outcome_5d={
            "return_5d_pct": -2.1,
            "max_favorable_5d_pct": 1.0,
            "max_adverse_5d_pct": -4.0,
        },
    )


def test_exit_model_shadow_records_are_upserted_by_as_of_trade_date() -> None:
    db = _db()

    record_exit_model_shadow(db, _record(as_of="2026-05-20T10:30:00", confidence=0.8))
    record_exit_model_shadow(db, _record(as_of="2026-05-20T14:30:00", confidence=0.9))
    db.commit()

    rows = db.execute(select(MarketModelObservation)).scalars().all()
    assert len(rows) == 1
    assert rows[0].model_key == EXIT_MODEL_OBSERVATION_KEY
    assert rows[0].trade_date == "2026-05-20"
    assert rows[0].confidence == 0.9
    payload = json.loads(rows[0].payload_json)
    assert payload["as_of"] == "2026-05-20T14:30:00"
    assert payload["feature_snapshot"]["feature_values"]["pnl_pct"] == 6.0


def test_exit_model_shadow_latest_and_summary_include_fallback_and_sell_flying() -> None:
    db = _db()
    fallback = _record(as_of="2026-05-21T10:30:00", confidence=0.0)
    fallback = ExitModelShadowRecord(
        **{
            **fallback.to_dict(),
            "model_action": "hold",
            "fallback_reason": "model_unavailable",
            "outcome_5d": {"return_5d_pct": 3.0, "max_favorable_5d_pct": 6.0, "max_adverse_5d_pct": -0.5},
        }
    )
    hard_stop = ExitModelShadowRecord(
        **{
            **_record(as_of="2026-05-22T10:30:00").to_dict(),
            "rule_action": "hard_stop",
            "model_action": "sell_all",
            "fallback_reason": "hard_stop_rule_priority",
        }
    )
    for item in (_record(), fallback, hard_stop):
        record_exit_model_shadow(db, item)
    db.commit()

    latest = latest_exit_model_shadow_records(db, limit=10)
    summary = summarize_exit_model_shadow(db, lookback_days=3650)

    assert len(latest) == 3
    assert summary["model_key"] == EXIT_MODEL_OBSERVATION_KEY
    assert summary["fallback_count"] == 2
    assert summary["hard_stop_shadow_count"] == 1


def test_exit_model_dataset_uses_time_ordered_split() -> None:
    dataset = build_exit_model_dataset(synthetic_exit_model_records(30))

    assert dataset.metadata["temporal_order_enforced"] is True
    assert dataset.metadata["sample_count"] >= 30
    assert dataset.train_rows
    assert dataset.validation_rows
    assert dataset.test_rows
    assert max(row["as_of"] for row in dataset.train_rows) <= min(row["as_of"] for row in dataset.validation_rows)


def test_evaluate_exit_model_shadow_smoke_script_outputs_metrics() -> None:
    script = Path("/Users/j/Documents/gupiao/research/scripts/evaluate_exit_model_shadow.py")

    result = subprocess.run(
        [sys.executable, str(script), "--smoke"],
        cwd="/Users/j/Documents/gupiao",
        check=True,
        text=True,
        capture_output=True,
    )

    payload = json.loads(result.stdout)
    assert payload["version"] == "exit-model-shadow-evaluation-v1"
    assert payload["smoke"] is True
    assert payload["record_count"] >= 10
    assert "fallback_rate_pct" in payload["summary"]
