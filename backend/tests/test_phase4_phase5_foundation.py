from __future__ import annotations

from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.entities import BacktestRun, PaperAccount
from app.models.schema_defs.phase4 import (
    AgentQualityScoreRequest,
    MLSignalPredictionRequest,
    PaperBacktestComparisonRequest,
    QuantParameterSetCreate,
    RuntimeTaskCreate,
)
from app.services.agent_quality import score_agent_result
from app.services.market.providers import DataSourceProbeService
from app.services.ml_signal import MLSignalService
from app.services.paper.backtest_compare import PaperBacktestComparisonService
from app.services.quant import QuantParameterVersionService
from app.services.tasks import RuntimeTaskQueue


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


def test_runtime_task_queue_records_events_and_status():
    db = _db()
    queue = RuntimeTaskQueue(db)

    created = queue.enqueue(RuntimeTaskCreate(task_type="noop", payload={"ok": True}))
    claimed = queue.claim_next(worker_id="test-worker")
    assert claimed is not None
    assert claimed.id == created.id
    finished = queue.mark_succeeded(created.id, {"done": True})

    assert finished.status == "succeeded"
    events = queue.events(created.id)
    assert [event.event_type for event in events] == ["queued", "started", "succeeded"]


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
    assert created.version == "test-params-v2"
    assert service.current().version == "test-params-v2"


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
