from __future__ import annotations

from app.models.schema_defs.phase4 import MLSignalPredictionRequest, MLSignalPredictionResponse
from app.services.ml_signal.features import signal_label, to_float

HEURISTIC_MODEL_KEY = "research-heuristic-v1"


def heuristic_predict(payload: MLSignalPredictionRequest, warning: str = "") -> MLSignalPredictionResponse:
    features = payload.features or {}
    score = 0.5
    reasons: list[str] = []
    if to_float(features.get("priority_score")) >= 80:
        score += 0.18
        reasons.append("优先级分数较高。")
    if to_float(features.get("risk_score")) >= 6:
        score -= 0.2
        reasons.append("风险分偏高。")
    shrink_ratio = to_float(features.get("volume_shrink_ratio"))
    if shrink_ratio and shrink_ratio <= 0.8:
        score += 0.08
        reasons.append("缩量承接特征较好。")
    probability = round(min(max(score, 0.0), 1.0), 3)
    return MLSignalPredictionResponse(
        symbol=payload.symbol,
        model_key=payload.model_key or HEURISTIC_MODEL_KEY,
        model_type="heuristic",
        research_only=True,
        probability=probability,
        label=signal_label(probability),  # type: ignore[arg-type]
        confidence=round(abs(probability - 0.5) * 2, 3),
        reasons=reasons or ["未找到 production 模型，输出启发式研究结果。"],
        warning=warning or "研究模型输出，不进入生产交易建议。",
    )
