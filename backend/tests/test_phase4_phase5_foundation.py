from __future__ import annotations

from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.entities import BacktestRun, MLSignalModel, MLSignalSample, PaperAccount
from app.models.schema_defs.phase4 import (
    AgentQualityScoreRequest,
    MLSignalPredictionRequest,
    MLSignalTrainRequest,
    PaperBacktestComparisonRequest,
    QuantParameterSetCreate,
    RuntimeTaskCreate,
)
from app.models.schema_defs.market import (
    IntradayAnomalyResponse,
    SectorEtfT0Opportunity,
    SectorEtfT0Response,
)
from app.services.agent_quality import score_agent_result
from app.services.intraday_anomaly import IntradayAnomalyService
from app.services.low_buy.screening import LowBuyScreeningMixin
from app.services.low_buy.service import LowBuyScreenerService
from app.services.market.providers import DataSourceProbeService
from app.services.ml_signal import MLSignalService
from app.services.paper.backtest_compare import PaperBacktestComparisonService
from app.services.quant import QuantParameterVersionService
from app.services.sector_etf_t0 import SectorEtfT0Service
from app.services.tasks import RuntimeTaskQueue
from app.workers import runtime_worker


def _db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return session_factory()


def test_agent_quality_blocks_incomplete_executable_result():
    response = score_agent_result(
        AgentQualityScoreRequest(
            provider="hermes",
            trace_id="trace-1",
            input_payload={"risk_control": {"blocked": True}},
            output_payload={"final_action": "positive_t", "confidence": 0.9},
        ),
        persist=False,
    )

    assert response.passed is False
    assert response.blocked is True
    assert any(issue.code == "action_conflicts_with_risk" for issue in response.issues)


def test_runtime_task_queue_records_events_and_status(monkeypatch):
    db = _db()
    queue = RuntimeTaskQueue(db)
    published = []

    monkeypatch.setattr("app.services.tasks.queue.publish_runtime_task_event", lambda event: published.append(event.event_type))

    created = queue.enqueue(RuntimeTaskCreate(task_type="noop", payload={"ok": True}))
    claimed = queue.claim_next(worker_id="test-worker")
    assert claimed is not None
    assert claimed.id == created.id
    finished = queue.mark_succeeded(created.id, {"done": True})

    assert finished.status == "succeeded"
    events = queue.events(created.id)
    assert [event.event_type for event in events] == ["queued", "started", "succeeded"]
    assert published == ["queued", "started", "succeeded"]


def test_runtime_worker_executes_monitor_snapshot_refresh(monkeypatch):
    db = _db()
    calls = []

    def _build_stub(db_arg, *, user_id: int, priority_limit: int):  # noqa: ANN001
        calls.append((db_arg, user_id, priority_limit))
        return {"ok": True, "user_id": user_id, "priority_limit": priority_limit}

    monkeypatch.setattr(runtime_worker, "build_and_store_monitor_snapshot", _build_stub)

    result = runtime_worker._execute_task(
        "monitor_snapshot_refresh",
        {"user_id": 3, "priority_limit": 99},
        db,
    )

    assert result == {"ok": True, "user_id": 3, "priority_limit": 30}
    assert calls == [(db, 3, 30)]


def test_low_buy_runtime_cache_methods_use_runtime_state():
    runtime = LowBuyScreenerService()._runtime

    assert runtime._get_screen_cache("missing-screen-cache") is None
    assert runtime._get_daily_history_cache("missing-daily-history-cache") is None
    runtime._set_spot_quote_cache({"600000": {"last_price": 10.0}})

    assert runtime._get_spot_quote_cache() == {"600000": {"last_price": 10.0}}


def test_quant_parameter_version_default_and_create():
    db = _db()
    service = QuantParameterVersionService(db)

    current = service.current()
    created = service.create(
        QuantParameterSetCreate(
            version="test-params-v2",
            scope="global",
            params={"risk": {"max_single_position_pct": 0.2}},
            activate=True,
        ),
        created_by="tester",
    )

    assert current.version
    assert "strategy_prefilters" in current.params["low_buy"]
    assert "strategy_execution" in current.params["low_buy"]
    assert "scoring" in current.params["low_buy"]
    assert "thresholds" in current.params["low_buy"]
    assert "auto_governance" in current.params["low_buy"]
    assert "research_layers" in current.params["low_buy"]
    assert "hard_risk" in current.params["low_buy"]
    assert "dynamic_adjustment" in current.params["low_buy"]
    assert "market" in current.params
    assert "regime_scoring" in current.params["market"]
    assert "normalizers" in current.params["market"]["regime_scoring"]
    assert current.params["low_buy"]["scoring"]["base_score"] > 0
    assert created.version == "test-params-v2"
    assert service.current().version == "test-params-v2"
    assert "strategy_prefilters" in service.current().params["low_buy"]


def test_quant_parameter_current_prefers_exact_scope_over_newer_global():
    db = _db()
    service = QuantParameterVersionService(db)

    service.create(
        QuantParameterSetCreate(
            version="low-buy-specific",
            scope="low_buy",
            params={"low_buy": {"min_priority_score": 81}},
            activate=True,
        ),
        created_by="tester",
    )
    service.create(
        QuantParameterSetCreate(
            version="newer-global",
            scope="global",
            params={"low_buy": {"min_priority_score": 70}},
            activate=True,
        ),
        created_by="tester",
    )

    assert service.current(scope="low_buy").version == "low-buy-specific"
    assert service.current(scope="global").version == "newer-global"


def test_data_source_probe_reports_configured_chain():
    response = DataSourceProbeService().probe()

    assert response.provider_order
    assert response.items
    assert all(item.source for item in response.items)


def test_ml_signal_prediction_is_research_only():
    db = _db()
    response = MLSignalService(db).predict(
        MLSignalPredictionRequest(
            symbol="600000",
            features={"priority_score": 88, "risk_score": 2, "volume_shrink_ratio": 0.75},
        )
    )

    assert response.research_only is True
    assert response.probability > 0.5
    assert response.label in {"positive", "neutral", "negative"}


def test_ml_signal_training_blocks_small_sample_production(tmp_path, monkeypatch):
    db = _db()
    monkeypatch.setenv("ML_SIGNAL_MODEL_DIR", str(tmp_path))
    from app.core.config import get_settings

    get_settings.cache_clear()
    for index in range(120):
        db.add(
            MLSignalSample(
                sample_key=f"sample:{index}",
                symbol="600000",
                trade_date="2026-05-06",
                strategy_key="first_board",
                source="backtest",
                feature_json=(
                    '{"price": %s, "quantity": 100, "gross_amount": %s, '
                    '"strategy_known": 1, "market_state_known": 1, "is_sell": 0, '
                    '"priority_score": %s, "risk_score": %s, "volume_shrink_ratio": 0.7}'
                    % (10 + index / 10, 1000 + index, 80 + index % 10, index % 5)
                ),
                label_json='{"pnl_pct": 1.5}' if index % 2 == 0 else '{"pnl_pct": -1.0}',
            )
        )
    db.commit()

    service = MLSignalService(db)
    trained = service.train(
        MLSignalTrainRequest(
            model_key="test-logistic",
            model_type="logistic",
            source="backtest",
            min_samples=100,
            limit=120,
            promote=True,
            min_validation_accuracy=0.5,
        )
    )
    predicted = service.predict(
        MLSignalPredictionRequest(
            symbol="600000",
            model_key="test-logistic",
            features={"price": 11.0, "quantity": 100, "gross_amount": 1100, "strategy_known": 1},
        )
    )

    assert trained.status == "research"
    assert trained.artifact_uri
    assert "样本量不足" in trained.metrics["promotion_blocked_reason"]
    assert predicted.research_only is True
    assert predicted.model_key == "test-logistic"
    get_settings.cache_clear()


def test_ml_signal_rejects_artifact_path_outside_model_dir(tmp_path, monkeypatch):
    db = _db()
    model_dir = tmp_path / "models"
    outside_file = tmp_path / "unsafe.pkl"
    outside_file.write_bytes(b"not a trusted pickle")
    monkeypatch.setenv("ML_SIGNAL_MODEL_DIR", str(model_dir))
    from app.core.config import get_settings

    get_settings.cache_clear()
    db.add(
        MLSignalModel(
            model_key="unsafe-model",
            model_type="logistic",
            status="production",
            feature_schema_json='{"feature_names": []}',
            metrics_json=(
                '{"sample_count": 2000, "validation_accuracy": 0.8, '
                '"validation_auc": 0.75, "artifact_sha256": "unused"}'
            ),
            artifact_uri=str(outside_file),
        )
    )
    db.commit()

    response = MLSignalService(db).predict(
        MLSignalPredictionRequest(
            symbol="600000",
            model_key="unsafe-model",
            features={"priority_score": 88, "risk_score": 2},
        )
    )

    assert response.research_only is True
    assert "降级启发式" in response.warning
    get_settings.cache_clear()


def test_low_buy_runtime_uses_composition_adapter_seam():
    runtime = LowBuyScreenerService()._runtime

    assert not isinstance(runtime, LowBuyScreeningMixin)
    assert callable(runtime.screen)
    assert callable(runtime.priority_board)


def test_sector_etf_validation_reports_acceptance_from_current_opportunities(monkeypatch):
    db = _db()
    service = SectorEtfT0Service()

    def _build_stub(db_arg, *, limit: int = 8):  # noqa: ANN001
        return SectorEtfT0Response(
            updated_at="2026-05-07 10:00:00",
            market_state="repair",
            market_state_text="震荡修复",
            total=2,
            opportunities=[
                SectorEtfT0Opportunity(
                    sector_name="半导体",
                    etf_symbol="512480",
                    etf_name="半导体ETF",
                    bias="positive_t",
                    confidence=72,
                    expected_edge_pct=1.05,
                ),
                SectorEtfT0Opportunity(
                    sector_name="证券",
                    etf_symbol="512880",
                    etf_name="证券ETF",
                    bias="positive_t",
                    confidence=66,
                    expected_edge_pct=0.95,
                ),
            ],
        )

    monkeypatch.setattr(service, "build", _build_stub)

    report = service.validation_report(db, limit=2)

    assert report.model_key == "sector_etf_t0"
    assert report.production_ready is True
    assert report.metrics[0].sample_count == 2


def test_intraday_anomaly_validation_requires_structured_outputs(monkeypatch):
    service = IntradayAnomalyService()

    def _detect_stub(symbol: str):  # noqa: ANN001
        return IntradayAnomalyResponse(
            symbol=symbol,
            name=symbol,
            updated_at="2026-05-07 10:00:00",
            anomaly_level="watch",
            anomaly_text="需要观察",
            score=22,
            pattern="拉伸加速",
            action_hint="只观察，不追高。",
            risk_notes=["冲高回落风险"],
        )

    monkeypatch.setattr(service, "detect", _detect_stub)

    report = service.validation_report(["600000", "000001", "601318", "510300", "512480"])

    assert report.model_key == "intraday_anomaly"
    assert report.production_ready is True
    assert report.metrics[0].sample_count == 5


def test_paper_backtest_comparison_flags_large_deviation():
    db = _db()
    account = PaperAccount(
        name="test",
        initial_cash=Decimal("100000.00"),
        total_assets=Decimal("90000.00"),
        cash_available=Decimal("90000.00"),
    )
    run = BacktestRun(
        name="run",
        status="succeeded",
        initial_cash=100000.0,
        final_equity=120000.0,
        strategy_keys="first_board",
    )
    db.add_all([account, run])
    db.commit()
    db.refresh(account)
    db.refresh(run)

    payload = PaperBacktestComparisonRequest(backtest_run_id=run.id, account_id=account.id, deviation_threshold_pct=20)
    response = PaperBacktestComparisonService(db).compare(
        account_id=payload.account_id or account.id,
        backtest_run_id=payload.backtest_run_id,
        deviation_threshold_pct=payload.deviation_threshold_pct,
    )

    assert response.alert is True
    assert response.expected_return_pct == 20.0
    assert response.actual_return_pct == -10.0
