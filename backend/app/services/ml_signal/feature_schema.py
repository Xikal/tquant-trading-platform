from __future__ import annotations

import hashlib
import json
from typing import Any

from app.services.ml_signal.features import FEATURE_NAMES


SCHEMA_VERSION = "ml_signal_features_v1"


def feature_schema_payload(feature_names: list[str] | None = None) -> dict[str, Any]:
    names = list(feature_names or FEATURE_NAMES)
    return {
        "schema_version": SCHEMA_VERSION,
        "feature_names": names,
        "feature_count": len(names),
        "feature_schema_hash": feature_schema_hash(names),
    }


def feature_schema_hash(feature_names: list[str] | None = None) -> str:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "feature_names": list(feature_names or FEATURE_NAMES),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def add_model_version_metadata(
    metrics: dict[str, Any],
    *,
    status: str,
    promotion_candidate: bool,
    promote_requested: bool,
) -> dict[str, Any]:
    schema_hash = feature_schema_hash()
    if status == "production":
        stage = "production"
        shadow_pct = 0.0
        canary_pct = 0.0
        production_pct = 100.0
    elif promotion_candidate and not promote_requested:
        stage = "staging"
        shadow_pct = 5.0
        canary_pct = 0.0
        production_pct = 0.0
    else:
        stage = "research"
        shadow_pct = 0.0
        canary_pct = 0.0
        production_pct = 0.0
    metrics.update(
        {
            "model_version_status": stage,
            "deployment_stage": stage,
            "shadow_traffic_pct": shadow_pct,
            "canary_traffic_pct": canary_pct,
            "production_traffic_pct": production_pct,
            "feature_schema_version": SCHEMA_VERSION,
            "feature_schema_hash": schema_hash,
            "offline_online_consistency": "feature_schema_hash_enforced",
        }
    )
    return metrics


def feature_schema_warning(
    *,
    artifact: dict[str, Any],
    metrics: dict[str, Any],
    row_schema: dict[str, Any],
) -> str:
    expected_names = list(FEATURE_NAMES)
    artifact_names = list(artifact.get("feature_names") or artifact.get("feature_schema", {}).get("feature_names") or [])
    if artifact_names != expected_names:
        return "模型 artifact 特征列表与当前线上特征列表不一致，已阻断 ML 推理。"
    expected_hash = feature_schema_hash(expected_names)
    artifact_hash = str(artifact.get("feature_schema_hash") or artifact.get("feature_schema", {}).get("feature_schema_hash") or "")
    metric_hash = str(metrics.get("feature_schema_hash") or "")
    row_hash = str(row_schema.get("feature_schema_hash") or "")
    if artifact_hash and artifact_hash != expected_hash:
        return "模型 artifact 特征签名与当前线上特征签名不一致，已阻断 ML 推理。"
    if metric_hash and metric_hash != expected_hash:
        return "模型记录特征签名与当前线上特征签名不一致，已阻断 ML 推理。"
    if row_hash and row_hash != expected_hash:
        return "模型 schema 特征签名与当前线上特征签名不一致，已阻断 ML 推理。"
    return ""
