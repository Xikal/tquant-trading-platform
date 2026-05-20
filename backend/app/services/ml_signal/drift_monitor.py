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
    psi_threshold: float = 0.20,
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
        kl_value = _kl_divergence(left, right)
        psi_value = _psi(left, right)
        item = {
            "feature": name,
            "kl_divergence": round(kl_value, 4),
            "psi": round(psi_value, 4),
            "status": "alert" if kl_value > kl_threshold or psi_value > psi_threshold else "ok",
        }
        items.append(item)
        if kl_value > kl_threshold or psi_value > psi_threshold:
            alerts.append(f"{name} 分布漂移 KL={kl_value:.3f} / PSI={psi_value:.3f}，建议进入 Watch 观察。")
    performance = _performance_degradation(recent, baseline)
    alerts.extend(performance.get("alerts", []))
    return {
        "ready": True,
        "alerts": alerts,
        "items": sorted(items, key=lambda item: max(float(item["kl_divergence"]), float(item["psi"])), reverse=True)[:12],
        "performance": performance,
    }


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


def _psi(recent: np.ndarray, baseline: np.ndarray) -> float:
    combined = np.concatenate([recent, baseline])
    if len(combined) == 0 or float(np.nanmax(combined)) == float(np.nanmin(combined)):
        return 0.0
    bins = np.histogram_bin_edges(combined, bins=10)
    actual, _ = np.histogram(recent, bins=bins, density=False)
    expected, _ = np.histogram(baseline, bins=bins, density=False)
    actual = actual.astype(float) + 1e-6
    expected = expected.astype(float) + 1e-6
    actual = actual / actual.sum()
    expected = expected / expected.sum()
    return float(np.sum((actual - expected) * np.log(actual / expected)))


def _performance_degradation(recent: list[MLSignalSample], baseline: list[MLSignalSample]) -> dict[str, Any]:
    recent_labels = _labels(recent)
    baseline_labels = _labels(baseline)
    if len(recent_labels) < 30 or len(baseline_labels) < 30:
        return {"ready": False, "alerts": []}
    recent_rate = sum(recent_labels) / len(recent_labels)
    baseline_rate = sum(baseline_labels) / len(baseline_labels)
    threshold = max(0.45, baseline_rate - 0.12)
    alerts: list[str] = []
    if recent_rate < threshold:
        alerts.append(f"近期 ML 闭环胜率 {recent_rate:.1%} 低于退化阈值 {threshold:.1%}，建议触发重训或降级观察。")
    if _five_day_degraded(recent, threshold):
        alerts.append("最近 5 个有样本交易日的闭环胜率持续偏低，建议暂停模型自动晋级。")
    return {
        "ready": True,
        "recent_positive_rate": round(recent_rate, 4),
        "baseline_positive_rate": round(baseline_rate, 4),
        "degradation_threshold": round(threshold, 4),
        "alerts": alerts,
    }


def _labels(rows: list[MLSignalSample]) -> list[int]:
    values: list[int] = []
    for row in rows:
        try:
            payload = json.loads(row.label_json or "{}")
        except Exception:
            continue
        if "return_pct" in payload:
            values.append(1 if float(payload.get("return_pct") or 0) > 0 else 0)
        elif "pnl_pct" in payload:
            values.append(1 if float(payload.get("pnl_pct") or 0) > 0 else 0)
        elif "pnl_amount" in payload:
            values.append(1 if float(payload.get("pnl_amount") or 0) > 0 else 0)
    return values


def _five_day_degraded(rows: list[MLSignalSample], threshold: float) -> bool:
    by_date: dict[str, list[int]] = {}
    for row in rows:
        labels = _labels([row])
        if not labels:
            continue
        by_date.setdefault(str(row.trade_date or ""), []).extend(labels)
    recent_dates = [date for date in sorted(by_date.keys(), reverse=True) if by_date[date]][:5]
    if len(recent_dates) < 5:
        return False
    return all(sum(by_date[date]) / len(by_date[date]) < threshold for date in recent_dates)
