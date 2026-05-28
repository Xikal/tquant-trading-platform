from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.entities import MarketModelObservation
from app.services.low_buy.main_force_model_schema import MAIN_FORCE_MODEL_OBSERVATION_KEY
from app.services.paper import main_force_paper_advisor as advisor
from app.services.paper.main_force_paper_advisor import build_main_force_paper_advice, latest_main_force_advice_for_symbol
from backend.tests.main_force_model_test_helpers import main_force_candidate


def test_paper_advice_is_readonly_when_suggestion_disabled() -> None:
    result = build_main_force_paper_advice(
        candidate=main_force_candidate(),
        main_force_advice=_advice(),
        risk_allowed=True,
    )

    assert result["visible"] is True
    assert result["mode"] == "readonly_shadow"
    assert result["suggestion_enabled"] is False
    assert result["order_intent"] == "none"


def test_paper_suggestion_requires_risk_and_clean_advice(monkeypatch) -> None:
    monkeypatch.setattr(advisor, "get_settings", lambda: _settings(suggestion_enabled=True))

    blocked = build_main_force_paper_advice(
        candidate=main_force_candidate(),
        main_force_advice=_advice(),
        risk_allowed=False,
    )
    risky = build_main_force_paper_advice(
        candidate=main_force_candidate(),
        main_force_advice=_advice(risk_flags=["风险阻断"]),
        risk_allowed=True,
    )

    assert blocked["suggestion_enabled"] is False
    assert any("风控" in item for item in blocked["risk_flags"])
    assert risky["suggestion_enabled"] is False
    assert any("风险阻断" in item for item in risky["risk_flags"])


def test_paper_suggestion_caps_position_and_stays_manual(monkeypatch) -> None:
    monkeypatch.setattr(advisor, "get_settings", lambda: _settings(suggestion_enabled=True))

    result = build_main_force_paper_advice(
        candidate=main_force_candidate(final_position_cap_pct=8.0, suggested_position_pct=8.0),
        main_force_advice=_advice(action="buy_confirmed", confidence=0.8),
        risk_allowed=True,
        current_position_pct=1.0,
    )

    assert result["suggestion_enabled"] is True
    assert result["mode"] == "paper_small_position_suggestion"
    assert result["position_cap_pct"] == 2.0
    assert result["order_intent"] == "manual_import_only"


def test_latest_main_force_advice_for_symbol_reads_shadow_payload() -> None:
    db = _db()
    db.add(
        MarketModelObservation(
            model_key=MAIN_FORCE_MODEL_OBSERVATION_KEY,
            symbol="300001",
            name="测试科技",
            trade_date="2026-04-24",
            signal_state="buy_probe",
            confidence=0.7,
            payload_json='{"model_advice":{"stage":"washout","stage_text":"洗盘确认","action":"buy_probe","action_text":"小仓试买","score":68.5,"confidence":0.7}}',
            outcome_status="pending",
        )
    )
    db.commit()

    result = latest_main_force_advice_for_symbol(db, "300001")

    assert result["action"] == "buy_probe"
    assert result["shadow_trade_date"] == "2026-04-24"
    assert result["shadow_outcome_status"] == "pending"


def _settings(*, suggestion_enabled: bool) -> SimpleNamespace:
    return SimpleNamespace(
        main_force_model_enabled=True,
        main_force_model_paper_display_enabled=True,
        main_force_model_paper_suggestion_enabled=suggestion_enabled,
        main_force_model_paper_max_position_pct=3.0,
        main_force_model_paper_min_confidence=0.62,
    )


def _advice(
    *,
    action: str = "buy_probe",
    stage: str = "washout",
    confidence: float = 0.7,
    risk_flags: list[str] | None = None,
) -> dict:
    return {
        "stage": stage,
        "stage_text": "洗盘确认",
        "action": action,
        "action_text": "小仓试买",
        "score": 68.5,
        "confidence": confidence,
        "reasons": ["近 10 日出现适中回撤。"],
        "risk_flags": risk_flags or [],
        "fallback_reason": None,
    }


def _db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()
