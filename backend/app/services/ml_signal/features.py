from __future__ import annotations

import json
import math
from decimal import Decimal
from typing import Any

import numpy as np

from app.models.entities import DailyBarSnapshot, MLSignalSample


FEATURE_NAMES = [
    "price",
    "quantity",
    "gross_amount",
    "strategy_known",
    "market_state_known",
    "is_sell",
    "priority_score",
    "risk_score",
    "volume_shrink_ratio",
    "price_momentum_5d",
    "price_momentum_10d",
    "volume_slope_5d",
    "volume_slope_10d",
    "price_momentum_5d_z",
    "price_momentum_10d_z",
    "volume_slope_5d_z",
    "volume_slope_10d_z",
    "sector_relative_strength_5d",
    "sector_relative_strength_10d",
]


def trade_features(
    *,
    price: float,
    quantity: int,
    gross_amount: float,
    strategy_key: str,
    market_state: str,
    side: str,
    sequence_features: dict[str, float] | None = None,
) -> dict[str, Any]:
    features = {
        "price": price,
        "quantity": quantity,
        "gross_amount": gross_amount,
        "strategy_known": 1 if strategy_key else 0,
        "market_state_known": 1 if market_state else 0,
        "is_sell": 1 if side == "sell" else 0,
        "priority_score": 0.0,
        "risk_score": 0.0,
        "volume_shrink_ratio": 0.0,
    }
    features.update(sequence_features or empty_sequence_features())
    return features


def empty_sequence_features() -> dict[str, float]:
    return {
        "price_momentum_5d": 0.0,
        "price_momentum_10d": 0.0,
        "volume_slope_5d": 0.0,
        "volume_slope_10d": 0.0,
        "price_momentum_5d_z": 0.0,
        "price_momentum_10d_z": 0.0,
        "volume_slope_5d_z": 0.0,
        "volume_slope_10d_z": 0.0,
        "sector_relative_strength_5d": 0.0,
        "sector_relative_strength_10d": 0.0,
    }


def sequence_features_from_bars(rows: list[DailyBarSnapshot]) -> dict[str, float]:
    if not rows:
        return empty_sequence_features()
    closes = [float(row.close_price or 0.0) for row in rows if float(row.close_price or 0.0) > 0]
    volumes = [float(row.volume or 0.0) for row in rows if float(row.volume or 0.0) >= 0]
    latest_close = closes[-1] if closes else 0.0

    def momentum_at(index: int, days: int) -> float:
        if index - days < 0:
            return 0.0
        start = closes[index - days]
        end = closes[index]
        if start <= 0 or end <= 0:
            return 0.0
        return (end / start - 1.0) * 100

    def momentum(days: int) -> float:
        if latest_close <= 0 or len(closes) <= days or closes[-days - 1] <= 0:
            return 0.0
        return round(momentum_at(len(closes) - 1, days), 4)

    def slope_for_series(series: list[float]) -> float:
        if len(series) < 3:
            return 0.0
        avg_volume = float(np.mean(series)) or 1.0
        x_values = np.arange(len(series), dtype=float)
        coef = float(np.polyfit(x_values, np.asarray(series, dtype=float), 1)[0])
        return coef / avg_volume

    def slope(days: int) -> float:
        series = volumes[-days:] if len(volumes) >= days else volumes
        return round(slope_for_series(series), 6)

    def rolling_momentum_z(days: int) -> float:
        values = [momentum_at(index, days) for index in range(days, len(closes))]
        return zscore(values[-1] if values else 0.0, values)

    def rolling_slope_z(days: int) -> float:
        values = [slope_for_series(volumes[max(0, index - days + 1) : index + 1]) for index in range(days - 1, len(volumes))]
        return zscore(values[-1] if values else 0.0, values)

    return {
        "price_momentum_5d": momentum(5),
        "price_momentum_10d": momentum(10),
        "volume_slope_5d": slope(5),
        "volume_slope_10d": slope(10),
        "price_momentum_5d_z": rolling_momentum_z(5),
        "price_momentum_10d_z": rolling_momentum_z(10),
        "volume_slope_5d_z": rolling_slope_z(5),
        "volume_slope_10d_z": rolling_slope_z(10),
    }


def label_is_positive(label: dict[str, Any]) -> bool:
    if "return_pct" in label:
        return to_float(label.get("return_pct")) > 0
    if "pnl_pct" in label:
        return to_float(label.get("pnl_pct")) > 0
    if "pnl_amount" in label:
        return to_float(label.get("pnl_amount")) > 0
    return to_float(label.get("net_amount")) > 0


def samples_to_matrix(rows: list[MLSignalSample]) -> tuple[np.ndarray, np.ndarray]:
    x_rows: list[list[float]] = []
    labels: list[int] = []
    for row in rows:
        features = json_dict(row.feature_json)
        label = json_dict(row.label_json)
        x_rows.append([to_float(features.get(name)) for name in FEATURE_NAMES])
        labels.append(1 if label_is_positive(label) else 0)
    return np.asarray(x_rows, dtype=float), np.asarray(labels, dtype=int)


def predict_probability(estimator: Any, features: dict[str, Any]) -> float:
    x_matrix = np.asarray([[to_float(features.get(name)) for name in FEATURE_NAMES]], dtype=float)
    probability = float(estimator_probabilities(estimator, x_matrix)[0])
    return round(min(max(probability, 0.0), 1.0), 3)


def estimator_probabilities(estimator: Any, x_matrix: np.ndarray) -> np.ndarray:
    if hasattr(estimator, "predict_proba"):
        values = estimator.predict_proba(x_matrix)
        return np.asarray(values[:, 1], dtype=float)
    values = estimator.predict(x_matrix)
    return np.asarray(values, dtype=float)


def signal_label(probability: float) -> str:
    if probability >= 0.62:
        return "positive"
    if probability <= 0.38:
        return "negative"
    return "neutral"


def zscore(value: float, values: list[float]) -> float:
    if len(values) < 5:
        return 0.0
    array = np.asarray([item for item in values if math.isfinite(float(item))], dtype=float)
    if len(array) < 5:
        return 0.0
    std = float(np.std(array))
    if std <= 1e-9:
        return 0.0
    return round((float(value) - float(np.mean(array))) / std, 4)


def safe_float(value: Decimal | float | int | str | None) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def to_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def json_dict(raw: str) -> dict[str, Any]:
    try:
        value = json.loads(raw or "{}")
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}
