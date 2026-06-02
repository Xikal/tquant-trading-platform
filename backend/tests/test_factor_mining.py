from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import factor_mining
from app.core.admin_auth import require_admin_auth
from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.base import Base
from app.models.entities import DailyBarSnapshot, User
from app.models.schema_defs.factor_mining import FactorCreateRequest, FactorEvaluationRequest
from app.services.factor_mining.combination import ridge_regression_combination
from app.services.factor_mining.compute_engine import FactorComputeEngine, FactorSafetyError
from app.services.factor_mining.evaluation import _daily_rank_ic, _walk_forward_ic
from app.services.factor_mining.hypothesis_agent import FactorHypothesisAgent
from app.services.factor_mining.library import FactorLibrary
from app.services.factor_mining.orchestrator import FactorMiningOrchestrator
from app.services.factor_mining.scheduler import monthly_factor_mining_topic


def _db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return factory()


def _seed_bars(db) -> None:  # noqa: ANN001
    start = date(2026, 1, 1)
    for symbol_index in range(30):
        symbol = f"600{symbol_index:03d}"
        base = 10 + symbol_index * 0.1
        for day in range(60):
            close = base + day * (0.01 + symbol_index * 0.0005)
            db.add(
                DailyBarSnapshot(
                    symbol=symbol,
                    trade_date=(start + timedelta(days=day)).isoformat(),
                    open_price=close * 0.99,
                    close_price=close,
                    high_price=close * 1.02,
                    low_price=close * 0.98,
                    volume=100000 + symbol_index * 1000 + day * 100,
                    amount=(100000 + symbol_index * 1000 + day * 100) * close,
                    pct_chg=0.5,
                    pre_close=close * 0.995,
                )
            )
    db.commit()


def test_factor_compute_engine_blocks_unsafe_code():
    unsafe = "import os\ndef compute_factor(bars):\n    return bars['close_price']"
    try:
        FactorComputeEngine().validate(unsafe)
    except FactorSafetyError:
        return
    raise AssertionError("unsafe factor code should be rejected")


def test_factor_compute_engine_blocks_loops_and_file_readers():
    unsafe_loop = "def compute_factor(bars):\n    while True:\n        pass\n    return bars['close_price']"
    unsafe_reader = "def compute_factor(bars):\n    return pd.read_csv('/tmp/secret.csv')['x']"
    for code in (unsafe_loop, unsafe_reader):
        try:
            FactorComputeEngine().validate(code)
        except FactorSafetyError:
            continue
        raise AssertionError("unsafe factor code should be rejected")


def test_factor_compute_engine_does_not_execute_top_level_code_in_main_process():
    formula = (
        "1 / 0\n"
        "def compute_factor(bars):\n"
        "    return bars['close_price'].astype(float)\n"
    )
    try:
        FactorComputeEngine(timeout_seconds=5, parallel_workers=1).compute(
            formula,
            pd.DataFrame(
                [
                    {"symbol": "600000", "trade_date": "2026-01-01", "close_price": 10.0},
                    {"symbol": "600000", "trade_date": "2026-01-02", "close_price": 10.2},
                ]
            ),
        )
    except FactorSafetyError:
        return
    else:
        raise AssertionError("top-level executable factor code should be rejected before execution")


def test_factor_compute_engine_rejects_top_level_executable_statements():
    formula = (
        "pd.set_option('display.max_rows', 999)\n"
        "def compute_factor(bars):\n"
        "    return bars['close_price'].astype(float)\n"
    )
    try:
        FactorComputeEngine().validate(formula)
    except FactorSafetyError:
        return
    raise AssertionError("top-level executable factor code should be rejected")


def test_walk_forward_ic_requires_stable_rolling_oos_windows():
    dates = pd.bdate_range("2025-01-01", periods=180)
    values = pd.Series([0.04] * 140 + [-0.02] * 40, index=[item.date().isoformat() for item in dates])

    windows = _walk_forward_ic(values, train_months=3, oos_months=1, min_train_days=40, min_oos_days=5)

    assert windows
    assert any(value < 0 for value in windows)


def test_daily_rank_ic_uses_rust_when_available(monkeypatch):
    calls = []

    def fake_rank_ic(factors, returns):
        calls.append((factors, returns))
        return 0.42

    monkeypatch.setattr("app.services.factor_mining.evaluation.rust_rank_ic", fake_rank_ic)
    samples = pd.DataFrame(
        [
            {"trade_date": "2026-05-25", "symbol": "600000", "factor_value": 1.0, "future_return": 0.01},
            {"trade_date": "2026-05-25", "symbol": "600001", "factor_value": 2.0, "future_return": 0.02},
            {"trade_date": "2026-05-25", "symbol": "600002", "factor_value": 3.0, "future_return": 0.03},
        ]
    )

    values = _daily_rank_ic(samples, min_cross_section=3)

    assert calls
    assert values.iloc[0] == 0.42


def test_monthly_factor_mining_topic_rotates_research_domains():
    january = monthly_factor_mining_topic(date(2026, 1, 1))
    february = monthly_factor_mining_topic(date(2026, 2, 1))

    assert january != february


def test_hypothesis_agent_generates_at_least_twenty_without_llm():
    db = _db()
    response = FactorHypothesisAgent(db).generate(topic="量价结构", count=20, use_llm=False)
    assert response.provider == "deepseek-v4-flash"
    assert len(response.items) == 20
    assert response.items[0].data_deps


def test_factor_evaluation_records_metrics():
    db = _db()
    _seed_bars(db)
    formula = (
        "def compute_factor(bars):\n"
        "    close = bars['close_price'].astype(float)\n"
        "    return close.pct_change(5).shift(1).fillna(0.0)\n"
    )
    factor = FactorLibrary(db).create(
        FactorCreateRequest(
            factor_key="test_momentum",
            name="测试动量",
            hypothesis="测试",
            formula_code=formula,
        )
    )
    response = FactorMiningOrchestrator(db).evaluate_factor(
        factor.factor_key,
        FactorEvaluationRequest(limit_symbols=30, min_cross_section=10, holding_days=3),
    )
    assert response.result.observation_count > 0
    assert response.result.sample_days > 0
    assert isinstance(response.result.information_ratio, float)
    assert response.run_id is not None


def test_factor_mining_routes_basic_contract():
    db = _db()
    app = FastAPI()
    app.include_router(factor_mining.router, prefix="/api")
    user = User(id=1, username="tester", password_hash="x", roles="admin")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[require_admin_auth] = lambda: None
    client = TestClient(app)

    response = client.post("/api/factor-mining/hypotheses", json={"topic": "缩量", "count": 20, "use_llm": False})
    assert response.status_code == 200
    assert len(response.json()["items"]) == 20

    activation = client.put("/api/factor-mining/factors/demo/activation", json={"active": True})
    assert activation.status_code == 200
    assert activation.json() == {"factor_key": "demo", "active": True}

    ridge = client.post(
        "/api/factor-mining/combine",
        json={
            "method": "ridge",
            "factor_returns": {"a": [0.01, 0.02, 0.03, 0.04, 0.05], "b": [0.05, 0.04, 0.03, 0.02, 0.01]},
            "target_returns": [0.01, 0.02, 0.03, 0.04, 0.05],
        },
    )
    assert ridge.status_code == 200
    assert ridge.json()["method"] in {"ridge_regression", "equal_weight"}


def test_factor_mining_routes_require_research_permission():
    db = _db()
    app = FastAPI()
    app.include_router(factor_mining.router, prefix="/api")
    user = User(id=2, username="viewer", password_hash="x", roles="")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    client = TestClient(app)

    response = client.get("/api/factor-mining/factors")
    assert response.status_code == 403


def test_ridge_regression_combination_prefers_predictive_factor():
    result = ridge_regression_combination(
        {"a": [0.01, 0.02, 0.03, 0.04, 0.05, 0.06], "b": [0.06, 0.05, 0.04, 0.03, 0.02, 0.01]},
        [0.01, 0.02, 0.03, 0.04, 0.05, 0.06],
    )
    assert result.weights["a"] > result.weights["b"]
