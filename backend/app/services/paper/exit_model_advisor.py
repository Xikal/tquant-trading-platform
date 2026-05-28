from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import Any

from app.core.config import BACKEND_DIR, get_settings
from app.services.paper.exit_model_schema import EXIT_MODEL_VERSION, ExitModelFeatureSnapshot, ExitModelSuggestion

ACTION_RANK = {
    "hold": 0,
    "sell_30": 1,
    "sell_50": 2,
    "sell_70": 3,
    "sell_all": 4,
    "hard_stop": 5,
}


class ExitModelAdvisor:
    """Shadow-only advisor around the production dynamic-exit rule system."""

    def suggest(self, features: ExitModelFeatureSnapshot) -> ExitModelSuggestion:
        settings = get_settings()
        if not bool(getattr(settings, "paper_exit_model_enabled", True)):
            return self._fallback(features, "disabled")
        if features.rule_action == "hard_stop":
            return ExitModelSuggestion(
                action="sell_all",
                confidence=1.0,
                pullback_risk=1.0,
                expected_return_next=0.0,
                suggested_trailing_stop_pct=0.0,
                reasons=["hard_stop_rule_priority"],
                model_version=EXIT_MODEL_VERSION,
                feature_snapshot=features.to_dict(),
                fallback_reason="hard_stop_rule_priority",
                shadow_only=True,
                data_quality=features.data_quality,
                rule_action=features.rule_action,
                rule_sell_ratio=features.rule_sell_ratio,
                effective_action=features.rule_action,
                safety_blocked=True,
            )
        if features.data_quality != "fresh":
            return self._fallback(features, f"data_quality_{features.data_quality}")
        model_payload = _load_model_payload(str(getattr(settings, "paper_exit_model_artifact_path", "") or ""))
        if model_payload is None:
            return self._fallback(features, "model_unavailable")
        try:
            raw = _predict_payload(model_payload, features)
        except Exception:
            return self._fallback(features, "model_error")
        suggestion = _suggestion_from_prediction(raw, features)
        min_confidence = float(getattr(settings, "paper_exit_model_min_confidence", 0.55) or 0.55)
        if suggestion.confidence < min_confidence:
            low_confidence = ExitModelSuggestion(
                **{
                    **suggestion.to_dict(),
                    "action": "hold",
                    "fallback_reason": "low_confidence",
                    "effective_action": features.rule_action,
                }
            )
            return _enforce_rule_floor(low_confidence, features)
        return _enforce_rule_floor(suggestion, features)

    def _fallback(self, features: ExitModelFeatureSnapshot, reason: str) -> ExitModelSuggestion:
        rule_rank = ACTION_RANK.get(features.rule_action, 0)
        return ExitModelSuggestion(
            action=_action_for_rank(rule_rank),  # type: ignore[arg-type]
            confidence=0.0,
            pullback_risk=0.0,
            expected_return_next=0.0,
            suggested_trailing_stop_pct=0.0,
            reasons=[reason],
            model_version=EXIT_MODEL_VERSION,
            feature_snapshot=features.to_dict(),
            fallback_reason=reason,
            shadow_only=True,
            data_quality=features.data_quality,
            rule_action=features.rule_action,
            rule_sell_ratio=features.rule_sell_ratio,
            effective_action=features.rule_action,
            safety_blocked=rule_rank > ACTION_RANK["hold"],
        )


def _load_model_payload(raw_path: str) -> dict[str, Any] | None:
    if not raw_path:
        return None
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = BACKEND_DIR / path
    if not path.exists() or not path.is_file():
        return None
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else None
    with path.open("rb") as file:
        payload = pickle.load(file)
    return payload if isinstance(payload, dict) else None


def _predict_payload(model_payload: dict[str, Any], features: ExitModelFeatureSnapshot) -> dict[str, Any]:
    estimator = model_payload.get("estimator")
    feature_names = list(model_payload.get("feature_names") or sorted(features.feature_values.keys()))
    vector = [[float(features.feature_values.get(name, 0.0) or 0.0) for name in feature_names]]
    if estimator is not None:
        probabilities = _estimator_probabilities(estimator, vector)
        pullback_risk = float(probabilities[0])
        return {
            "pullback_risk": pullback_risk,
            "confidence": max(pullback_risk, 1.0 - pullback_risk),
            "expected_return_next": 0.0,
            "action": _action_from_risk(pullback_risk),
            "reasons": ["tabular_model_prediction"],
            "model_version": str(model_payload.get("model_version") or EXIT_MODEL_VERSION),
        }
    weights = dict(model_payload.get("weights") or {})
    intercept = float(model_payload.get("intercept", 0.0) or 0.0)
    score = intercept + sum(float(weights.get(name, 0.0) or 0.0) * float(features.feature_values.get(name, 0.0) or 0.0) for name in feature_names)
    pullback_risk = max(0.0, min(1.0, score))
    return {
        "pullback_risk": pullback_risk,
        "confidence": float(model_payload.get("confidence", max(pullback_risk, 1.0 - pullback_risk)) or 0.0),
        "expected_return_next": float(model_payload.get("expected_return_next", 0.0) or 0.0),
        "action": str(model_payload.get("action") or _action_from_risk(pullback_risk)),
        "reasons": list(model_payload.get("reasons") or ["linear_shadow_model"]),
        "model_version": str(model_payload.get("model_version") or EXIT_MODEL_VERSION),
    }


def _estimator_probabilities(estimator: Any, vector: list[list[float]]) -> list[float]:
    if hasattr(estimator, "predict_proba"):
        probabilities = estimator.predict_proba(vector)
        return [float(row[-1]) for row in probabilities]
    predictions = estimator.predict(vector)
    return [float(item) for item in predictions]


def _suggestion_from_prediction(raw: dict[str, Any], features: ExitModelFeatureSnapshot) -> ExitModelSuggestion:
    action = str(raw.get("action") or "hold")
    if action not in ACTION_RANK or action == "hard_stop":
        action = "hold"
    return ExitModelSuggestion(
        action=action,  # type: ignore[arg-type]
        confidence=round(max(0.0, min(float(raw.get("confidence", 0.0) or 0.0), 1.0)), 4),
        pullback_risk=round(max(0.0, min(float(raw.get("pullback_risk", 0.0) or 0.0), 1.0)), 4),
        expected_return_next=round(float(raw.get("expected_return_next", 0.0) or 0.0), 4),
        suggested_trailing_stop_pct=round(_suggested_trailing_stop(features), 4),
        reasons=[str(item) for item in raw.get("reasons", []) if str(item)],
        model_version=str(raw.get("model_version") or EXIT_MODEL_VERSION),
        feature_snapshot=features.to_dict(),
        fallback_reason=None,
        shadow_only=True,
        data_quality=features.data_quality,
        rule_action=features.rule_action,
        rule_sell_ratio=features.rule_sell_ratio,
        effective_action=features.rule_action,
        safety_blocked=False,
    )


def _enforce_rule_floor(suggestion: ExitModelSuggestion, features: ExitModelFeatureSnapshot) -> ExitModelSuggestion:
    rule_rank = ACTION_RANK.get(features.rule_action, 0)
    model_rank = ACTION_RANK.get(suggestion.action, 0)
    if model_rank < rule_rank:
        return ExitModelSuggestion(
            **{
                **suggestion.to_dict(),
                "action": _action_for_rank(rule_rank),
                "fallback_reason": "rule_action_floor",
                "effective_action": features.rule_action,
                "safety_blocked": True,
            }
        )
    return ExitModelSuggestion(
        **{
            **suggestion.to_dict(),
            "effective_action": features.rule_action,
        }
    )


def _action_from_risk(risk: float) -> str:
    if risk >= 0.88:
        return "sell_all"
    if risk >= 0.78:
        return "sell_70"
    if risk >= 0.68:
        return "sell_50"
    if risk >= 0.58:
        return "sell_30"
    return "hold"


def _action_for_rank(rank: int) -> str:
    for action, value in ACTION_RANK.items():
        if value == rank and action != "hard_stop":
            return action
    return "sell_all" if rank >= ACTION_RANK["sell_all"] else "hold"


def _suggested_trailing_stop(features: ExitModelFeatureSnapshot) -> float:
    if features.pnl_pct >= 8:
        return 1.2
    if features.pnl_pct >= 5:
        return 1.6
    if features.pnl_pct >= 3:
        return 2.0
    return 0.0
