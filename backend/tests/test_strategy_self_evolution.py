from __future__ import annotations

import json
from datetime import datetime
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.entities import BacktestValidation, MLSignalModel, QuantParameterSet
from app.runtime.strategy_evolution_scheduler import self_evolution_due
from app.services.ml_signal.promotion_service import MLSignalPromotionService
from app.services.strategy_self_evolution import StrategySelfEvolutionOrchestrator
from app.workers.runtime_worker import _execute_task


def _db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()


def test_strategy_self_evolution_due_after_friday_close() -> None:
    assert self_evolution_due(datetime(2026, 5, 15, 16, 5)) is True
    assert self_evolution_due(datetime(2026, 5, 15, 15, 59)) is False
    assert self_evolution_due(datetime(2026, 5, 14, 16, 5)) is False


def test_manual_ml_model_promotion_requires_candidate() -> None:
    db = _db()
    db.add(
        MLSignalModel(
            model_key="research-a",
            model_type="xgboost",
            status="research",
            feature_schema_json=json.dumps({"feature_names": ["a"]}),
            metrics_json=json.dumps({"promotion_candidate": False, "promotion_blocked_reason": "样本不足"}),
            artifact_uri="local://a",
            artifact_checksum="abc",
        )
    )
    db.commit()

    try:
        MLSignalPromotionService(db).approve("research-a", operator="tester")
    except ValueError as exc:
        assert "样本不足" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError")


def test_manual_ml_model_promotion_switches_candidate_to_production(monkeypatch) -> None:
    db = _db()
    monkeypatch.setattr("app.services.ml_signal.promotion_service.production_model_warning", lambda status, metrics: "")
    db.add_all(
        [
            MLSignalModel(
                model_key="old-prod",
                model_type="xgboost",
                status="production",
                feature_schema_json=json.dumps({"feature_names": ["a"]}),
                metrics_json=json.dumps({"promotion_candidate": True, "artifact_sha256": "old"}),
                artifact_uri="local://old",
                artifact_checksum="old",
            ),
            MLSignalModel(
                model_key="new-candidate",
                model_type="xgboost",
                status="research",
                feature_schema_json=json.dumps({"feature_names": ["a"]}),
                metrics_json=json.dumps({"promotion_candidate": True, "approval_required": True}),
                artifact_uri="local://new",
                artifact_checksum="new",
            ),
        ]
    )
    db.commit()

    promoted = MLSignalPromotionService(db).approve("new-candidate", operator="tester")

    assert promoted.model_key == "new-candidate"
    assert promoted.metrics["approval_required"] is False
    assert db.query(MLSignalModel).filter_by(model_key="new-candidate").one().status == "production"
    assert db.query(MLSignalModel).filter_by(model_key="old-prod").one().status == "archived"


def test_manual_ml_model_promotion_revalidates_current_thresholds_before_archiving() -> None:
    db = _db()
    db.add_all(
        [
            MLSignalModel(
                model_key="old-prod",
                model_type="xgboost",
                status="production",
                feature_schema_json=json.dumps({"feature_names": ["a"]}),
                metrics_json=json.dumps({"promotion_candidate": True, "artifact_sha256": "old"}),
                artifact_uri="local://old",
                artifact_checksum="old",
            ),
            MLSignalModel(
                model_key="stale-candidate",
                model_type="xgboost",
                status="research",
                feature_schema_json=json.dumps({"feature_names": ["a"]}),
                metrics_json=json.dumps({"promotion_candidate": True, "approval_required": True}),
                artifact_uri="local://new",
                artifact_checksum="new",
            ),
        ]
    )
    db.commit()

    try:
        MLSignalPromotionService(db).approve("stale-candidate", operator="tester")
    except ValueError as exc:
        assert "当前生产门槛复核失败" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError")

    assert db.query(MLSignalModel).filter_by(model_key="old-prod").one().status == "production"
    assert db.query(MLSignalModel).filter_by(model_key="stale-candidate").one().status == "research"


def test_strategy_self_evolution_runtime_task(monkeypatch) -> None:
    db = _db()

    def _run_stub(self, payload):  # noqa: ANN001
        return {"ok": True, "payload": payload}

    monkeypatch.setattr(StrategySelfEvolutionOrchestrator, "run", _run_stub)

    result = _execute_task("strategy_self_evolution", {"min_samples": 100}, db)

    assert result == {"ok": True, "payload": {"min_samples": 100}}


def test_strategy_self_evolution_orchestrator_marks_human_approval(monkeypatch) -> None:
    db = _db()

    train = SimpleNamespace(
        model_key="candidate",
        status="research",
        warning="等待审批",
        metrics={"promotion_candidate": True, "approval_required": True},
        model_dump=lambda mode="json": {"model_key": "candidate", "status": "research"},
    )
    status = SimpleNamespace(
        drift_ready=True,
        drift_alerts=["漂移提示"],
        drift_items=[{"feature": "x"}],
        model_dump=lambda mode="json": {"drift_ready": True},
    )
    monkeypatch.setattr("app.services.strategy_self_evolution.MLSignalService.incremental_train", lambda self, payload: train)
    monkeypatch.setattr("app.services.strategy_self_evolution.MLSignalService.online_learning_status", lambda self, min_samples=100: status)
    monkeypatch.setattr("app.services.strategy_self_evolution.build_low_buy_strategy_governance", lambda db: SimpleNamespace(items=[]))

    result = StrategySelfEvolutionOrchestrator(db).run({"min_samples": 100})

    assert result["human_approval_required"] is True
    assert result["model_approval"]["required"] is True
    assert result["drift_monitor"]["ready"] is True


def test_strategy_self_evolution_parameter_proposal_deduplicates_validation() -> None:
    db = _db()
    db.add(
        BacktestValidation(
            id=99,
            name="validation",
            status="succeeded",
            strategy_key="first_board",
            result_json=json.dumps(
                {
                    "best_params_by_market_state": {"repair": {"min_score": 72}},
                    "by_market_state": {"repair": {"window_count": 4, "pass_rate": 0.75, "signal_count": 80}},
                }
            ),
        )
    )
    db.commit()

    first = StrategySelfEvolutionOrchestrator(db)._propose_regime_parameters(operator="tester")
    second = StrategySelfEvolutionOrchestrator(db)._propose_regime_parameters(operator="tester")

    assert first["promoted_count"] == 1
    assert second["promoted_count"] == 0
    assert "已生成过参数草案" in second["skipped"][0]["reason"]
    drafts = db.query(QuantParameterSet).filter(QuantParameterSet.status == "draft").all()
    assert len(drafts) == 1
    assert "source_validation_id=99" in drafts[0].description
