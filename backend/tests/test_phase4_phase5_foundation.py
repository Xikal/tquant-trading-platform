from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.entities import (
    BacktestRun,
    BacktestTrade,
    DailyBarSnapshot,
    Instrument,
    MarketModelObservation,
    MLSignalModel,
    MLSignalSample,
    PaperAccount,
    PaperTrade,
    RuntimeTask,
)
from app.models.schemas import KlineBar, QuoteSnapshot
from app.models.schema_defs.phase4 import (
    AgentQualityScoreRequest,
    MLSignalPredictionRequest,
    StrategyCapacityRequest,
    MLSignalTrainRequest,
    PaperBacktestComparisonRequest,
    QuantParameterSetCreate,
    RuntimeTaskCreate,
)
from app.models.schema_defs.market import (
    IntradayAnomalyResponse,
    PairedHedgeResearchResponse,
    SectorEtfT0Opportunity,
    SectorEtfT0Response,
)
from app.services.agent_quality import score_agent_result
from app.services.distribution_signals import build_daily_distribution_snapshot
from app.services.intraday_anomaly import IntradayAnomalyService
from app.services.low_buy.screening import LowBuyScreeningMixin
from app.services.low_buy.service import LowBuyScreenerService
from app.services.market.providers import DataSourceProbeService
from app.services.market_model_observation_service import MarketModelObservationService
from app.services.ml_signal import MLSignalService
from app.services.paired_hedge_research import PairedHedgeResearchService
from app.services.paper.backtest_compare import PaperBacktestComparisonService
from app.services.quant import QuantParameterVersionService
from app.services.quant_engine_intraday_structure import classify_intraday_structure
from app.services.sector_etf_t0 import SectorEtfT0Service
from app.services.strategy_capacity import StrategyCapacityService
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


def test_runtime_task_queue_recovers_stale_running_idempotent_task(monkeypatch):
    db = _db()
    queue = RuntimeTaskQueue(db)
    published = []

    monkeypatch.setattr("app.services.tasks.queue.publish_runtime_task_event", lambda event: published.append(event.event_type))

    created = queue.enqueue(
        RuntimeTaskCreate(
            task_type="monitor_snapshot_refresh",
            payload={"user_id": 3, "priority_limit": 12},
            idempotency_key="monitor_snapshot_refresh:3:12",
            max_attempts=2,
        )
    )
    row = db.get(RuntimeTask, created.id)
    assert row is not None
    row.status = "running"
    row.locked_by = "dead-worker"
    row.locked_at = datetime.utcnow() - timedelta(minutes=30)
    row.attempt_count = 1
    db.commit()

    enqueued = queue.enqueue(
        RuntimeTaskCreate(
            task_type="monitor_snapshot_refresh",
            payload={"user_id": 3, "priority_limit": 12},
            idempotency_key="monitor_snapshot_refresh:3:12",
            max_attempts=2,
        )
    )
    claimed = queue.claim_next(worker_id="new-worker")

    assert enqueued.id == created.id
    assert claimed is not None
    assert claimed.id == created.id
    assert claimed.status == "running"
    assert claimed.locked_by == "new-worker"
    assert claimed.attempt_count == 2
    assert "retry" in published


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
    assert "distribution_signals" in current.params["market"]
    assert "intraday_structure" in current.params["position_t"]
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


def test_quant_parameter_version_rejects_invalid_numeric_boundary():
    db = _db()
    service = QuantParameterVersionService(db)

    try:
        service.create(
            QuantParameterSetCreate(
                version="invalid-negative",
                scope="low_buy",
                params={"low_buy": {"strategy_prefilters": {"first_board": {"min_volume_burst_ratio": -1}}}},
                activate=False,
            ),
            created_by="tester",
        )
    except ValueError as exc:
        assert "不能低于" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("negative bounded parameter should be rejected")

    try:
        service.create(
            QuantParameterSetCreate(
                version="invalid-score-max",
                scope="low_buy",
                params={"low_buy": {"min_priority_score": 999}},
                activate=False,
            ),
            created_by="tester",
        )
    except ValueError as exc:
        assert "不能高于" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("over-large score parameter should be rejected")


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


def test_ml_signal_artifact_storage_check_validates_remote_filesystem(tmp_path, monkeypatch):
    db = _db()
    model_dir = tmp_path / "models"
    remote_dir = tmp_path / "remote-artifacts"
    monkeypatch.setenv("ML_SIGNAL_MODEL_DIR", str(model_dir))
    monkeypatch.setenv("ML_SIGNAL_ARTIFACT_REMOTE_DIR", str(remote_dir))
    from app.core.config import get_settings

    get_settings.cache_clear()
    response = MLSignalService(db).check_artifact_storage()

    assert response.ok is True
    assert response.configured is True
    assert response.backend == "filesystem"
    assert response.write_ok is True
    assert response.read_ok is True
    assert response.restore_ok is True
    assert response.cleanup_ok is True
    assert not list(remote_dir.glob("storage_probe_*.pkl"))
    assert not list(model_dir.glob("restore_storage_probe_*.pkl"))
    get_settings.cache_clear()


def test_ml_signal_closed_paper_trade_outcome_is_persisted():
    db = _db()
    trade = PaperTrade(
        id=7,
        order_id=11,
        account_id=1,
        symbol="600000",
        side="sell",
        price=Decimal("10.80"),
        quantity=100,
        gross_amount=Decimal("1080.00"),
        commission=Decimal("5.00"),
        stamp_tax=Decimal("1.08"),
        transfer_fee=Decimal("0.00"),
        net_amount=Decimal("1073.92"),
        strategy_key="first_board",
    )
    db.add(trade)
    db.commit()

    created = MLSignalService(db).persist_paper_trade_outcome(
        trade,
        cost_basis=Decimal("10.00"),
        pnl_amount=Decimal("73.92"),
        return_pct=Decimal("8.00"),
    )
    db.commit()
    sample = db.query(MLSignalSample).filter(MLSignalSample.sample_key == "paper_close:7").one()

    assert created is True
    assert sample.source == "paper"
    assert '"return_pct": 8.0' in sample.label_json
    assert "price_momentum_5d_z" in sample.feature_json


def test_ml_signal_sequence_features_include_zscore_and_sector_strength():
    db = _db()
    db.add_all(
        [
            Instrument(symbol="600000", name="浦发银行", instrument_type="stock", sector_name="银行"),
            Instrument(symbol="512800", name="银行ETF", instrument_type="fund", sector_name="银行"),
        ]
    )
    for index in range(1, 16):
        trade_date = f"2026-04-{index:02d}"
        db.add(
            DailyBarSnapshot(
                symbol="600000",
                trade_date=trade_date,
                close_price=10 + index * 0.2,
                volume=10000 + index * 500,
                amount=1000000 + index * 10000,
                pct_chg=1.0,
            )
        )
        db.add(
            DailyBarSnapshot(
                symbol="512800",
                trade_date=trade_date,
                close_price=10 + index * 0.05,
                volume=9000 + index * 100,
                amount=900000 + index * 5000,
                pct_chg=0.2,
            )
        )
    db.commit()

    features = MLSignalService(db)._sequence_features("600000", "2026-04-15")

    assert "price_momentum_5d_z" in features
    assert "volume_slope_10d_z" in features
    assert features["sector_relative_strength_5d"] > 0


def test_ml_signal_online_learning_status_summarizes_closed_samples():
    db = _db()
    for index, return_pct in enumerate([2.1, -0.8, 1.4], start=1):
        db.add(
            MLSignalSample(
                sample_key=f"paper_close:{index}",
                symbol="600000",
                trade_date="2026-05-08",
                strategy_key="first_board",
                source="paper",
                feature_json='{"price": 10, "quantity": 100}',
                label_json=f'{{"closed": true, "return_pct": {return_pct}}}',
            )
        )
    db.add(RuntimeTask(task_type="ml_signal_incremental_train", status="succeeded", progress_pct=100.0))
    db.commit()

    response = MLSignalService(db).online_learning_status(min_samples=3)

    assert response.paper_sample_count == 3
    assert response.closed_trade_sample_count == 3
    assert response.positive_sample_count == 2
    assert response.negative_sample_count == 1
    assert response.ready_for_training is True
    assert response.latest_incremental_task_status == "succeeded"


def test_strategy_capacity_outputs_capital_curve():
    db = _db()
    db.add(
        BacktestTrade(
            run_id=1,
            trade_date="2026-04-10",
            symbol="600000",
            strategy_key="first_board",
            side="sell",
            price=10.5,
            gross_amount=1050.0,
            pnl_pct=1.2,
            pnl_amount=12.0,
        )
    )
    for index in range(10):
        db.add(
            DailyBarSnapshot(
                symbol="600000",
                trade_date=f"2026-04-{index + 1:02d}",
                close_price=10 + index * 0.1,
                amount=100_000_000 + index * 1_000_000,
                pct_chg=0.6,
            )
        )
    db.commit()

    response = StrategyCapacityService(db).evaluate(
        StrategyCapacityRequest(strategies=["first_board"], capital_levels=[500000.0, 1000000.0])
    )

    assert response.items
    assert response.items[0].curve
    assert response.items[0].curve[0].capacity_status in {"可承载", "谨慎", "过载"}
    assert response.assumptions["impact_model"] == "Square-root market impact + simplified Almgren-Chriss + participation tier"
    assert response.items[0].impact_model == "sqrt_plus_almgren_chriss"
    assert response.items[0].curve[0].impact_model == "sqrt_plus_almgren_chriss"
    assert response.items[0].curve[0].order_amount == 500000.0
    assert response.items[0].curve[0].average_daily_amount > 0
    assert response.items[0].curve[0].impact_pct == response.items[0].curve[0].impact_cost_pct
    assert response.items[0].curve[0].impact_cost_pct >= 0
    assert response.items[0].curve[0].almgren_chriss_cost_pct >= 0
    assert response.items[0].curve[0].execution_slices >= 1


def test_runtime_worker_executes_ml_incremental_train_task(tmp_path, monkeypatch):
    db = _db()
    monkeypatch.setenv("ML_SIGNAL_MODEL_DIR", str(tmp_path))
    from app.core.config import get_settings

    get_settings.cache_clear()
    for index in range(120):
        db.add(
            MLSignalSample(
                sample_key=f"paper-close:{index}",
                symbol="600000",
                trade_date="2026-05-08",
                strategy_key="first_board",
                source="paper",
                feature_json=(
                    '{"price": %s, "quantity": 100, "gross_amount": %s, '
                    '"strategy_known": 1, "market_state_known": 1, "is_sell": 1, '
                    '"priority_score": %s, "risk_score": %s, "volume_shrink_ratio": 0.7}'
                    % (10 + index / 10, 1000 + index, 70 + index % 8, index % 5)
                ),
                label_json='{"return_pct": 1.2}' if index % 2 == 0 else '{"return_pct": -0.8}',
            )
        )
    db.commit()

    result = runtime_worker._execute_task(
        "ml_signal_incremental_train",
        {"model_type": "logistic", "limit": 120, "min_samples": 100, "promote": False},
        db,
    )

    assert result["status"] in {"research", "failed"}
    assert result["sample_count"] >= 120
    get_settings.cache_clear()


def test_low_buy_runtime_uses_composition_adapter_seam():
    runtime = LowBuyScreenerService()._runtime

    assert not isinstance(runtime, LowBuyScreeningMixin)
    assert runtime._adapters
    assert not any(isinstance(adapter, LowBuyScreeningMixin) for adapter in runtime._adapters)
    assert callable(runtime.screen)
    assert callable(runtime.priority_board)


def test_distribution_thresholds_are_runtime_parameterized(monkeypatch):
    monkeypatch.setattr(
        "app.services.quant.runtime_parameters.get_market_distribution_signals",
        lambda: {
            "false_breakout_high_multiplier": 1.005,
            "false_breakout_close_multiplier": 0.998,
        },
    )

    _, snapshot = build_daily_distribution_snapshot(
        open_price=9.95,
        high_price=10.07,
        low_price=9.90,
        close_price=9.96,
        latest_change_pct=0.2,
        breakout_level=10.0,
        reference_high=10.1,
        volume_burst_ratio=1.0,
        latest_volume_ratio=0.2,
        post_volume_ratio=0.2,
    )

    assert snapshot.false_breakout_flag is True


def test_intraday_structure_thresholds_are_runtime_parameterized(monkeypatch):
    monkeypatch.setattr(
        "app.services.quant.runtime_parameters.get_position_t_intraday_structure",
        lambda: {"min_bars": 10},
    )
    quote = QuoteSnapshot(
        symbol="600000",
        name="测试",
        market="SH",
        instrument_type="stock",
        last_price=10.0,
        change_pct=0.0,
        change_amount=0.0,
        open_price=10.0,
        high_price=10.2,
        low_price=9.8,
        prev_close=10.0,
        volume=1000,
        amount=10000,
        timestamp="2026-05-08 10:00:00",
    )
    bars = [
        KlineBar(timestamp=f"2026-05-08 10:0{idx}:00", open=10.0, close=10.0, high=10.1, low=9.9, volume=1000, amount=10000)
        for idx in range(6)
    ]
    snapshot = classify_intraday_structure(
        quote=quote,
        bars=bars,
        ma5=10.0,
        vwap_value=10.0,
        distribution=type(
            "Distribution",
            (),
            {
                "false_breakout_flag": False,
                "stall_after_volume_flag": False,
                "long_upper_shadow": False,
                "weak_close": False,
                "distribution_risk_score": 0.0,
            },
        )(),
    )

    assert snapshot.key == "insufficient_intraday"


def test_sector_etf_validation_reports_acceptance_from_current_opportunities(monkeypatch):
    db = _db()
    service = SectorEtfT0Service()

    def _build_stub(db_arg, *, limit: int = 8, record_observations: bool = True):  # noqa: ANN001, ARG001
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
    assert report.production_ready is False
    assert report.metrics[0].status == "passed"
    assert report.metrics[0].sample_count == 2
    assert report.metrics[1].pending_count >= 0
    assert report.metrics[1].p_value >= 0


def test_sector_etf_proxy_prefers_exact_sector_mapping():
    from app.services.sector_etf_t0 import _proxy_for_sector

    semiconductor = _proxy_for_sector("半导体")
    chip = _proxy_for_sector("芯片")

    assert semiconductor is not None
    assert chip is not None
    assert semiconductor.symbol == "512480"
    assert chip.symbol == "512760"


def test_paired_hedge_research_response_is_research_only():
    response = PairedHedgeResearchResponse(
        updated_at="2026-05-08 10:00:00",
        total=0,
        ideas=[],
    )

    assert response.mode == "research_only"


def test_paired_hedge_research_builds_from_priority_board(monkeypatch):
    class _Quote:
        def __init__(self, last_price: float, change_pct: float) -> None:
            self.last_price = last_price
            self.change_pct = change_pct

    class _MarketData:
        def get_quotes_batch(self, symbols):  # noqa: ANN001
            return {
                "000001": _Quote(10.0, 1.2),
                "512480": _Quote(1.2, 0.4),
            }

    service = PairedHedgeResearchService(market_data=_MarketData())
    board = {
        "items": [
            {
                "symbol": "000001",
                "name": "测试股份",
                "sector_name": "半导体",
                "strategy_title": "首板回调",
                "priority_score": 92,
                "change_pct": 1.2,
            }
        ]
    }

    ideas = service.build_from_priority_board(board, limit=1)

    assert len(ideas) == 1
    assert ideas[0].legs[1].symbol == "512480"
    assert ideas[0].net_exposure_pct < 100


def test_market_model_observation_upserts_same_day_signal():
    db = _db()
    service = MarketModelObservationService()

    service.record(
        db,
        model_key="sector_etf_t0",
        symbol="512480",
        name="半导体ETF",
        signal_state="positive_t",
        confidence=61,
        expected_edge_pct=0.9,
        payload={"last_price": 1.2},
    )
    service.record(
        db,
        model_key="sector_etf_t0",
        symbol="512480",
        name="半导体ETF",
        signal_state="positive_t",
        confidence=72,
        expected_edge_pct=1.1,
        payload={"last_price": 1.25},
    )
    db.commit()

    rows = db.query(MarketModelObservation).all()
    assert len(rows) == 1
    assert rows[0].confidence == 72
    assert rows[0].expected_edge_pct == 1.1


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
    assert report.production_ready is False
    assert report.metrics[0].status == "passed"
    assert report.metrics[0].sample_count == 5
    assert report.metrics[1].false_positive_rate_pct >= 0
    assert report.metrics[1].p_value >= 0


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
