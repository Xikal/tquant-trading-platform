from __future__ import annotations

from datetime import date, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import factor_mining
from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.base import Base
from app.models.entities import DailyBarSnapshot, User
from app.models.schema_defs.factor_mining import FactorCreateRequest, FactorEvaluationRequest
from app.services.factor_mining.compute_engine import FactorComputeEngine, FactorSafetyError
from app.services.factor_mining.hypothesis_agent import FactorHypothesisAgent
from app.services.factor_mining.library import FactorLibrary
from app.services.factor_mining.orchestrator import FactorMiningOrchestrator


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
    client = TestClient(app)

    response = client.post("/api/factor-mining/hypotheses", json={"topic": "缩量", "count": 20, "use_llm": False})
    assert response.status_code == 200
    assert len(response.json()["items"]) == 20


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
