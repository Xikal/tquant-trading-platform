from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.models.entities import MLSignalModel
from app.models.schema_defs.phase4 import MLSignalTrainRequest
from app.services.ml_signal.modeling import json_dict


def load_warm_start_estimator(
    payload: MLSignalTrainRequest,
    *,
    select_model: Callable[[str | None], MLSignalModel | None],
    load_artifact: Callable[..., dict[str, Any]],
) -> Any | None:
    if payload.model_type != "xgboost":
        return None
    row = select_model("")
    if row is None or row.model_type != payload.model_type:
        return None
    try:
        metrics = json_dict(row.metrics_json)
        artifact = load_artifact(
            row.artifact_uri,
            expected_sha256=str(row.artifact_checksum or metrics.get("artifact_sha256") or ""),
            remote_artifact_uri=str(row.remote_artifact_uri or metrics.get("remote_artifact_uri") or ""),
        )
        return artifact.get("estimator")
    except Exception:
        return None
