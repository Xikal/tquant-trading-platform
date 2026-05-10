from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.entities import BacktestRun
from app.services.backtest_queue_metrics import backtest_queue_snapshot
from app.services.low_buy.atr_metrics import ATR_WINDOW, compute_daily_atr
from app.services.quant.parameter_version_service import default_quant_parameters


def _db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()


def test_ml_training_defaults_include_runtime_controls():
    training = default_quant_parameters()["ml"]["training"]
    assert training["cv_folds"] >= 2
    assert training["min_train_samples"] >= 20
    assert training["xgb_n_estimators"] == training["xgboost"]["n_estimators"]
    assert training["lgb_learning_rate"] == training["lightgbm"]["learning_rate"]


def test_backtest_queue_snapshot_reports_running_and_wait():
    db = _db()
    now = datetime.utcnow()
    db.add(BacktestRun(name="running", status="running", created_at=now - timedelta(minutes=3), started_at=now))
    queued = BacktestRun(name="queued", status="queued", created_at=now, initial_cash=100000, final_equity=100000)
    db.add(queued)
    db.commit()
    db.refresh(queued)

    snapshot = backtest_queue_snapshot(db, queued)

    assert snapshot.queue_depth == 1
    assert snapshot.queue_position == 1
    assert snapshot.running_count == 1
    assert snapshot.estimated_wait_seconds >= 0


def test_daily_atr_uses_true_range_window():
    frame = pd.DataFrame(
        [
            {"high": 10 + index, "low": 9 + index, "close": 9.5 + index}
            for index in range(ATR_WINDOW + 1)
        ]
    )

    assert compute_daily_atr(frame, ATR_WINDOW) > 0
