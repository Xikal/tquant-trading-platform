from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.core.config import get_settings
from app.services.low_buy.main_force_model_schema import (
    ACTION_TEXT,
    STAGE_TEXT,
    MainForceAdvice,
    MainForceFeatureSnapshot,
)


class MainForceAdvisor:
    """Shadow-only advisor for main-force accumulation/washout/markup structures."""

    def advise(self, features: MainForceFeatureSnapshot) -> MainForceAdvice:
        if features.data_quality not in {"fresh", "verified"}:
            return self._blocked(features, [f"数据质量为 {features.data_quality}，不参与买点增强。"], fallback_reason="data_quality")
        if features.risk_flags:
            return self._blocked(features, features.risk_flags)
        stage, score, reasons = _score_features(features)
        action = _action_for(stage, score)
        buy_zone = _buy_zone(features, stage)
        stop_loss = _stop_loss(features, stage)
        settings = get_settings()
        production_effect = "readonly_shadow" if settings.main_force_model_display_enabled else "none"
        return MainForceAdvice(
            stage=stage,
            stage_text=STAGE_TEXT.get(stage, "不可用"),
            action=action,
            action_text=ACTION_TEXT.get(action, "观察"),
            score=round(score, 2),
            confidence=round(min(max(score / 100.0, 0.0), 0.95), 4),
            buy_zone=buy_zone,
            stop_loss=stop_loss,
            take_profit_plan=_take_profit_plan(features.close_price),
            reasons=reasons,
            risk_flags=[],
            feature_snapshot=features.to_dict(),
            shadow_only=True,
            production_effect=production_effect,
        )

    def annotate_candidate(self, candidate: Any, features: MainForceFeatureSnapshot) -> Any:
        advice = self.advise(features).to_dict()
        if isinstance(candidate, dict):
            annotated = deepcopy(candidate)
            annotated["main_force_advice"] = advice
            return annotated
        if hasattr(candidate, "model_copy"):
            extra = dict(getattr(candidate, "model_extra", {}) or {})
            extra["main_force_advice"] = advice
            return candidate.model_copy(update=extra)
        annotated = deepcopy(candidate)
        setattr(annotated, "main_force_advice", advice)
        return annotated

    def _blocked(self, features: MainForceFeatureSnapshot, reasons: list[str], fallback_reason: str | None = None) -> MainForceAdvice:
        settings = get_settings()
        production_effect = "readonly_shadow" if settings.main_force_model_display_enabled else "none"
        return MainForceAdvice(
            stage="distribution_risk",
            stage_text=STAGE_TEXT["distribution_risk"],
            action="blocked",
            action_text=ACTION_TEXT["blocked"],
            score=0.0,
            confidence=0.0,
            buy_zone=(0.0, 0.0),
            stop_loss=0.0,
            reasons=[],
            risk_flags=list(reasons),
            feature_snapshot=features.to_dict(),
            shadow_only=True,
            production_effect=production_effect,
            fallback_reason=fallback_reason,
        )


def _score_features(features: MainForceFeatureSnapshot) -> tuple[str, float, list[str]]:
    accumulation = 0.0
    washout = 0.0
    markup = 0.0
    reasons: list[str] = []

    if 0.18 <= features.position_60d <= 0.72:
        accumulation += 16
        reasons.append("60 日位置不高，具备建仓观察空间。")
    if 8 <= features.range_20d_pct <= 38:
        accumulation += 12
        washout += 8
        reasons.append("20 日振幅适中，存在资金换手和洗盘空间。")
    if 0.9 <= features.amount_ratio_20d_60d <= 1.8:
        accumulation += 14
        reasons.append("20 日成交额相对 60 日温和抬升。")
    if -18 <= features.drawdown_10d_pct <= -5:
        washout += 22
        reasons.append("近 10 日出现适中回撤，符合洗盘候选。")
    if features.amount_ratio_5d_20d <= 1.12:
        washout += 12
        reasons.append("近 5 日量能未失控，洗盘质量较好。")
    if features.lower_shadow_ratio >= 0.18 or features.close_position_ratio >= 0.55:
        washout += 10
        reasons.append("下影或收盘位置显示承接。")
    if features.reclaim_ma10 or features.reclaim_ma20:
        markup += 18
        reasons.append("价格重新站回关键均线。")
    if features.platform_reclaim_20d:
        markup += 16
        reasons.append("接近或收回 20 日平台高点。")
    if 1.05 <= features.amount_ratio_1d_20d <= 2.5:
        markup += 10
        reasons.append("确认日成交额温和放大。")
    if features.trend_above_ma60:
        markup += 8
        accumulation += 4
        reasons.append("仍在 60 日趋势线上方。")
    if features.sector_strength >= 0.65:
        markup += 10
        reasons.append("板块强度支持拉升共振。")
    if features.market_state in {"repair", "weight_support", "weight_support_active", "fast_rotation"}:
        markup += 6
        reasons.append("市场状态允许结构性进攻。")

    scores = {
        "accumulation": accumulation,
        "washout": washout,
        "markup_confirm": markup,
    }
    stage = max(scores, key=scores.get)
    blended = scores[stage] + min(sum(value for key, value in scores.items() if key != stage) * 0.22, 18)
    return stage, min(blended, 100.0), reasons[:8]


def _action_for(stage: str, score: float) -> str:
    if score < 42:
        return "observe"
    if stage == "accumulation":
        return "wait_confirm"
    if stage == "washout":
        return "buy_probe" if score >= 55 else "wait_confirm"
    if stage == "markup_confirm":
        return "buy_confirmed" if score >= 62 else "buy_probe"
    return "observe"


def _buy_zone(features: MainForceFeatureSnapshot, stage: str) -> tuple[float, float]:
    close = features.close_price
    if close <= 0:
        return (0.0, 0.0)
    if stage == "washout":
        low = min(close * 0.985, max(features.ma10, features.ma20) * 0.99 if max(features.ma10, features.ma20) else close * 0.985)
        high = close * 1.012
    elif stage == "markup_confirm":
        low = close * 0.992
        high = close * 1.018
    else:
        low = close * 0.97
        high = close * 1.005
    return (round(low, 4), round(max(high, low), 4))


def _stop_loss(features: MainForceFeatureSnapshot, stage: str) -> float:
    close = features.close_price
    if close <= 0:
        return 0.0
    if stage == "markup_confirm":
        base = max(features.ma10, features.ma20 * 0.995 if features.ma20 else 0.0)
        return round(max(min(base, close * 0.965), close * 0.92), 4)
    if stage == "washout":
        base = features.ma20 * 0.985 if features.ma20 else close * 0.94
        return round(max(min(base, close * 0.955), close * 0.90), 4)
    return round(close * 0.92, 4)


def _take_profit_plan(close: float) -> list[dict[str, float | str]]:
    if close <= 0:
        return []
    return [
        {"level": "first", "price": round(close * 1.08, 4), "action": "sell_30"},
        {"level": "second", "price": round(close * 1.15, 4), "action": "sell_30"},
        {"level": "protect", "price": round(close * 1.22, 4), "action": "trailing_stop"},
    ]
