from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import analysis, backtests, factor_mining, ml_signals, paper_compare, paper_performance, research, screeners
from app.core.admin_auth import require_admin_auth
from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.paper_auth import require_paper_trading
from app.models.base import Base
from app.models.entities import BacktestRun, RuntimeTask, User
from app.models.schema_defs.screener_parts.priority import LowBuyPriorityBoardResponse


def _client(*, roles: str = "admin,backtest_research,backtest_optimizer", paper: bool = True) -> tuple[TestClient, sessionmaker]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    user = User(id=1, username="tester", password_hash="x", roles=roles, can_paper_trade=paper)

    def _db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(research.router, prefix="/api")
    app.include_router(screeners.router, prefix="/api")
    app.include_router(backtests.router, prefix="/api")
    app.include_router(ml_signals.router, prefix="/api")
    app.include_router(factor_mining.router, prefix="/api")
    app.include_router(analysis.router, prefix="/api")
    app.include_router(paper_performance.router, prefix="/api/paper")
    app.include_router(paper_compare.router, prefix="/api")
    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[require_admin_auth] = lambda: None
    app.dependency_overrides[require_paper_trading] = lambda: user
    return TestClient(app), factory


def test_legacy_research_backtest_is_queued() -> None:
    client, factory = _client()

    response = client.post("/api/backtests", json={"symbol": "600000", "lookback_bars": 720, "bar_period": "5m"})

    assert response.status_code == 202
    body = response.json()
    assert body["task_type"] == "legacy_research_backtest"
    assert body["payload"]["symbol"] == "600000"
    with factory() as db:
        task = db.execute(select(RuntimeTask).where(RuntimeTask.id == body["id"])).scalar_one()
        assert task.task_type == "legacy_research_backtest"


def test_low_buy_heavy_full_scan_is_queued(monkeypatch) -> None:
    client, _factory = _client()
    calls = []
    monkeypatch.setattr(screeners.low_buy_screener, "screen", lambda **kwargs: calls.append(kwargs) or None)

    response = client.get("/api/screeners/low-buy?strategy=first_board&scan_mode=full&scan_limit=480&limit=16")

    assert response.status_code == 202
    assert response.json()["task_type"] == "low_buy_materialization_refresh"
    assert calls == []


def test_low_buy_bounded_read_stays_sync(monkeypatch) -> None:
    client, _factory = _client()

    class _Result:
        items = []

        def model_dump(self):
            return {"items": [], "data_quality": "partial"}

    calls = []
    monkeypatch.setattr(screeners.low_buy_screener, "screen", lambda **kwargs: calls.append(kwargs) or _Result())
    monkeypatch.setattr(
        screeners,
        "UserSectorPreferenceService",
        lambda _db: type("S", (), {"get_excluded_sector_set": lambda _self, _user_id: set()})(),
    )
    monkeypatch.setattr(screeners, "filter_low_buy_screener_response", lambda result, _excluded: result)

    response = client.get("/api/screeners/low-buy?strategy=first_board&scan_mode=full&scan_limit=48&limit=16")

    assert response.status_code == 200
    assert response.json()["data_quality"] == "partial"
    assert calls and calls[0]["scan_limit"] == 48


def test_low_buy_execution_backtest_is_queued(monkeypatch) -> None:
    client, _factory = _client()
    monkeypatch.setattr(screeners.low_buy_screener, "execution_backtest", lambda **_kwargs: (_ for _ in ()).throw(AssertionError("should not run")))

    response = client.get("/api/screeners/low-buy/execution-backtest?strategy=first_board&lookback_days=60&limit=200")

    assert response.status_code == 202
    assert response.json()["task_type"] == "low_buy_execution_backtest"


def test_priority_board_web_sync_refresh_is_downgraded_to_async(monkeypatch) -> None:
    client, _factory = _client(roles="")
    calls = []

    def fake_priority_board(**kwargs):
        calls.append(kwargs)
        return LowBuyPriorityBoardResponse(
            as_of_date="2026-06-05",
            latest_trade_date="2026-06-05",
            updated_at="2026-06-05 10:00:00",
            refresh_queued=True,
            read_path="priority_board_read_model",
            items=[],
            family_sections=[],
            simple_buckets=[],
        )

    monkeypatch.setattr(screeners.low_buy_screener, "priority_board", fake_priority_board)
    monkeypatch.setattr(
        screeners,
        "UserSectorPreferenceService",
        lambda _db: type("S", (), {"get_excluded_sector_set": lambda _self, _user_id: set()})(),
    )
    monkeypatch.setattr(screeners, "filter_priority_board_response_for_user", lambda result, **_kwargs: result)
    monkeypatch.setattr(screeners, "apply_priority_board_live_overlay", lambda result: result)

    response = client.get("/api/screeners/low-buy/priority-board?limit=12&refresh=sync")

    assert response.status_code == 200
    assert calls and calls[0]["refresh_mode"] == "async"
    assert response.json()["read_path"] == "priority_board_read_model"


def test_large_etf_t0_research_is_queued() -> None:
    client, _factory = _client()
    bars = [_bar(index) for index in range(481)]

    response = client.post(
        "/api/backtests/etf-t0-research",
        json={
            "symbol": "510300",
            "name": "沪深300ETF",
            "quantity": 10000,
            "max_trades_per_day": 3,
            "min_signal_bars": 20,
            "bars": bars,
            "vwap_deviation_values": [0.25],
            "oversold_rsi_values": [34],
        },
    )

    assert response.status_code == 202
    assert response.json()["task_type"] == "etf_t0_research_report"


def test_portfolio_optimization_is_queued() -> None:
    client, factory = _client()
    with factory() as db:
        db.add(BacktestRun(id=9, owner_user_id=1, status="succeeded", strategy_keys="first_board", initial_cash=100000, final_equity=110000))
        db.commit()

    response = client.get("/api/backtests/9/portfolio-optimization?method=markowitz")

    assert response.status_code == 202
    assert response.json()["task_type"] == "backtest_portfolio_optimization"


def test_position_policy_shadow_training_is_queued(monkeypatch) -> None:
    client, factory = _client()
    with factory() as db:
        db.add(BacktestRun(id=10, owner_user_id=1, status="succeeded", strategy_keys="first_board"))
        db.commit()
    monkeypatch.setattr(backtests, "run_position_policy_research", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not run")))

    response = client.get("/api/backtests/10/position-policy-research?train_shadow=true")

    assert response.status_code == 202
    assert response.json()["task_type"] == "backtest_position_policy_research"


def test_ml_training_routes_are_queued() -> None:
    client, _factory = _client()

    samples = client.post("/api/ml/signals/samples", json={"source": "combined", "limit": 500, "persist": True})
    train = client.post("/api/ml/signals/train", json={"model_type": "logistic", "limit": 500, "min_samples": 100})
    incremental = client.post("/api/ml/signals/incremental-train", json={"model_type": "xgboost", "limit": 500, "min_samples": 100})

    assert samples.status_code == 202
    assert train.status_code == 202
    assert incremental.status_code == 202
    assert samples.json()["task_type"] == "ml_signal_build_samples"
    assert train.json()["task_type"] == "ml_signal_train"
    assert incremental.json()["task_type"] == "ml_signal_incremental_train"


def test_factor_direct_evaluate_and_iterate_are_queued() -> None:
    client, _factory = _client()

    evaluate = client.post(
        "/api/factor-mining/factors/demo/evaluate",
        json={"holding_days": 3, "limit_symbols": 100, "min_cross_section": 20},
    )
    iterate = client.post(
        "/api/factor-mining/iterate",
        json={
            "hypothesis": {
                "factor_name": "缩量修复",
                "factor_key": "volume_repair",
                "hypothesis": "缩量后修复",
                "data_deps": ["close_price", "volume"],
            },
            "rounds": 2,
            "evaluation": {"holding_days": 3},
        },
    )

    assert evaluate.status_code == 202
    assert iterate.status_code == 202
    assert evaluate.json()["task_type"] == "factor_mining_evaluate"
    assert iterate.json()["task_type"] == "factor_mining_iterate"


def test_analysis_batch_queue_flag_queues_without_running(monkeypatch) -> None:
    client, _factory = _client()
    monkeypatch.setattr(analysis.analysis_service, "analyze_batch", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not run")))

    response = client.post("/api/analyze/batch?queue=true", json=[{"symbol": "600000"}, {"symbol": "600001"}])

    assert response.status_code == 202
    assert response.json()["task_type"] == "analysis_batch"


def test_analysis_batch_openapi_has_generated_response_contract() -> None:
    client, _factory = _client()

    response_schema = (
        client.app.openapi()["paths"]["/api/analyze/batch"]["post"]["responses"]["200"]["content"]["application/json"]["schema"]
    )

    assert any(
        option.get("items", {}).get("$ref", "").endswith("/AnalysisResponse")
        for option in response_schema["anyOf"]
        if option.get("type") == "array"
    )


def test_paper_heavy_routes_are_queued() -> None:
    client, factory = _client()
    with factory() as db:
        db.add(BacktestRun(id=11, owner_user_id=1, status="succeeded", strategy_keys="first_board"))
        db.commit()

    smart_t = client.get("/api/paper/performance/smart-t-backtest?sample_limit=150")
    comparison = client.post("/api/paper/backtest-comparison", json={"backtest_run_id": 11})

    assert smart_t.status_code == 202
    assert comparison.status_code == 202
    assert smart_t.json()["task_type"] == "paper_smart_t_backtest"
    assert comparison.json()["task_type"] == "paper_backtest_comparison"


def _bar(index: int) -> dict:
    price = 10 + index * 0.001
    return {
        "timestamp": f"2026-06-04 09:{index % 60:02d}:00",
        "open": price,
        "high": price + 0.01,
        "low": price - 0.01,
        "close": price,
        "volume": 1000,
        "amount": price * 1000,
    }
