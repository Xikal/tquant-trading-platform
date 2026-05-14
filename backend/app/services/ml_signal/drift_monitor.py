from __future__ import annotations

import json
from typing import Any

import numpy as np

from app.models.entities import MLSignalSample
from app.services.ml_signal.features import FEATURE_NAMES


def feature_drift_summary(
    rows: list[MLSignalSample],
    *,
    recent_size: int = 200,
    baseline_size: int = 1000,
    kl_threshold: float = 0.25,
) -> dict[str, Any]:
    if len(rows) < recent_size + 50:
        return {"ready": False, "alerts": ["特征漂移样本不足，等待更多闭环样本。"], "items": []}
    recent = rows[:recent_size]
    baseline = rows[recent_size : recent_size + baseline_size]
    items: list[dict[str, Any]] = []
    alerts: list[str] = []
    for name in FEATURE_NAMES:
        left = _values(recent, name)
        right = _values(baseline, name)
        if len(left) < 30 or len(right) < 30:
            continue
        value = _kl_divergence(left, right)
        item = {"feature": name, "kl_divergence": round(value, 4), "status": "alert" if value > kl_threshold else "ok"}
        items.append(item)
        if value > kl_threshold:
            alerts.append(f"{name} 分布漂移 KL={value:.3f}，建议进入 Watch 观察。")
    return {"ready": True, "alerts": alerts, "items": sorted(items, key=lambda item: item["kl_divergence"], reverse=True)[:12]}


def _values(rows: list[MLSignalSample], key: str) -> np.ndarray:
    result: list[float] = []
    for row in rows:
        try:
            payload = json.loads(row.feature_json or "{}")
        except Exception:
            continue
        value = payload.get(key)
        try:
            result.append(float(value))
        except (TypeError, ValueError):
            continue
    return np.asarray(result, dtype=float)


def _kl_divergence(recent: np.ndarray, baseline: np.ndarray) -> float:
    combined = np.concatenate([recent, baseline])
    if len(combined) == 0 or float(np.nanmax(combined)) == float(np.nanmin(combined)):
        return 0.0
    bins = np.histogram_bin_edges(combined, bins=10)
    p, _ = np.histogram(recent, bins=bins, density=False)
    q, _ = np.histogram(baseline, bins=bins, density=False)
    p = p.astype(float) + 1e-6
    q = q.astype(float) + 1e-6
    p = p / p.sum()
    q = q / q.sum()
    return float(np.sum(p * np.log(p / q)))
