from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select

from app.models.entities import MarketModelObservation
from app.services.paper.exit_model_schema import EXIT_MODEL_OBSERVATION_KEY


FORBIDDEN_FUTURE_FEATURE_KEYWORDS = ("future", "next", "outcome", "t_plus", "t+")


def temporal_guard_checks(db, *, walk_forward: dict[str, Any]) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    if walk_forward.get("random_split_allowed") is not False:
        issues.append({"key": "random_time_series_split_not_forbidden", "severity": "blocking"})
    for window in walk_forward.get("windows") or []:
        if not _window_is_ordered(window):
            issues.append({"key": "walk_forward_window_order_violation", "severity": "blocking", "window": window})
    future_feature_rows = _future_feature_rows(db)
    issues.extend(future_feature_rows)
    return {
        "status": "pass" if not issues else "fail",
        "issues": issues[:50],
        "issue_count": len(issues),
        "checks": [
            "walk_forward_train_validation_oos_order",
            "random_time_series_split_forbidden",
            "exit_model_shadow_feature_snapshot_no_future_keys",
        ],
        "forbidden_feature_keywords": list(FORBIDDEN_FUTURE_FEATURE_KEYWORDS),
        "notes": [
            "T 日信号和模型特征只能使用当时可得数据；未来收益、结算 outcome、next/future 字段不得进入特征快照。",
            "Walk-forward 必须保持训练、验证、样本外严格时间顺序，禁止随机切分时间序列。",
        ],
    }


def _window_is_ordered(window: dict[str, Any]) -> bool:
    train_start = str(window.get("train_start") or "")
    train_end = str(window.get("train_end") or "")
    validation_start = str(window.get("validation_start") or "")
    validation_end = str(window.get("validation_end") or "")
    oos_start = str(window.get("oos_start") or "")
    oos_end = str(window.get("oos_end") or "")
    return bool(train_start and train_start <= train_end < validation_start <= validation_end < oos_start <= oos_end)


def _future_feature_rows(db) -> list[dict[str, Any]]:
    rows = (
        db.execute(
            select(MarketModelObservation)
            .where(MarketModelObservation.model_key == EXIT_MODEL_OBSERVATION_KEY)
            .order_by(MarketModelObservation.trade_date.desc(), MarketModelObservation.id.desc())
            .limit(500)
        )
        .scalars()
        .all()
    )
    issues = []
    for row in rows:
        payload = _json_dict(row.payload_json)
        feature_snapshot = payload.get("feature_snapshot") if isinstance(payload, dict) else {}
        forbidden = sorted(set(_find_forbidden_feature_keys(feature_snapshot if isinstance(feature_snapshot, dict) else {})))
        if forbidden:
            issues.append(
                {
                    "key": "exit_model_shadow_future_feature_keys",
                    "severity": "blocking",
                    "symbol": row.symbol,
                    "trade_date": row.trade_date,
                    "forbidden_keys": forbidden[:12],
                }
            )
    return issues


def _find_forbidden_feature_keys(payload: dict[str, Any], *, prefix: str = "") -> list[str]:
    found: list[str] = []
    for key, value in payload.items():
        dotted = f"{prefix}.{key}" if prefix else str(key)
        lowered = dotted.lower()
        if any(token in lowered for token in FORBIDDEN_FUTURE_FEATURE_KEYWORDS):
            found.append(dotted)
        if isinstance(value, dict):
            found.extend(_find_forbidden_feature_keys(value, prefix=dotted))
    return found


def _json_dict(value: str | None) -> dict[str, Any]:
    try:
        payload = json.loads(value or "{}")
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}
