from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.services.paper.exit_model_shadow import latest_exit_model_shadow_records


EXIT_MODEL_FEATURE_COLUMNS = [
    "pnl_pct",
    "max_profit_pct",
    "pullback_from_high_pct",
    "hold_days",
    "available_ratio",
    "position_pct",
    "vwap_deviation_pct",
    "rsi",
    "atr_pct",
    "high_pullback_ratio",
    "volume_release_ratio",
    "market_strength",
    "sector_strength",
    "rule_sell_ratio",
]


@dataclass(frozen=True)
class ExitModelDataset:
    feature_names: list[str]
    rows: list[dict[str, Any]]
    train_rows: list[dict[str, Any]]
    validation_rows: list[dict[str, Any]]
    test_rows: list[dict[str, Any]]
    metadata: dict[str, Any]


def build_exit_model_dataset_from_shadow(db: Session, *, limit: int = 5000) -> ExitModelDataset:
    return build_exit_model_dataset(latest_exit_model_shadow_records(db, limit=limit))


def build_exit_model_dataset(records: list[dict[str, Any]]) -> ExitModelDataset:
    rows = [_dataset_row(record) for record in records if _dataset_row(record) is not None]
    rows.sort(key=lambda item: item["as_of"])
    train, validation, test = _time_split(rows)
    return ExitModelDataset(
        feature_names=list(EXIT_MODEL_FEATURE_COLUMNS),
        rows=rows,
        train_rows=train,
        validation_rows=validation,
        test_rows=test,
        metadata={
            "sample_count": len(rows),
            "train_count": len(train),
            "validation_count": len(validation),
            "test_count": len(test),
            "split_method": "time_ordered_60_20_20",
            "temporal_order_enforced": True,
        },
    )


def synthetic_exit_model_records(sample_count: int = 80) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for index in range(max(10, sample_count)):
        pnl = (index % 12) - 3
        pullback = max(0, (index % 7) - 2) * 0.7
        risk = pnl >= 3 and pullback >= 1.4
        records.append(
            {
                "symbol": f"SIM{index:04d}",
                "name": "Synthetic",
                "strategy_key": "smoke",
                "as_of": f"2026-01-{index % 28 + 1:02d}T10:00:00",
                "rule_action": "hold",
                "rule_sell_ratio": 0.0,
                "model_action": "sell_50" if risk else "hold",
                "model_confidence": 0.8 if risk else 0.6,
                "feature_snapshot": {
                    "feature_values": {
                        "pnl_pct": float(pnl),
                        "max_profit_pct": float(pnl + pullback),
                        "pullback_from_high_pct": float(pullback),
                        "hold_days": float(index % 6),
                        "available_ratio": 1.0,
                        "position_pct": float(index % 10),
                        "vwap_deviation_pct": float((index % 5) - 2),
                        "rsi": 45.0 + float(index % 20),
                        "atr_pct": 1.2 + float(index % 3) * 0.2,
                        "high_pullback_ratio": pullback / 4,
                        "volume_release_ratio": 0.6 + float(index % 4) * 0.2,
                        "market_strength": float(index % 5) / 5,
                        "sector_strength": float(index % 7) / 7,
                        "rule_sell_ratio": 0.0,
                    }
                },
                "outcome_5d": {
                    "return_5d_pct": -1.2 if risk else 1.0,
                    "max_favorable_5d_pct": 2.0 if risk else 3.0,
                    "max_adverse_5d_pct": -3.0 if risk else -0.8,
                },
            }
        )
    return records


def _dataset_row(record: dict[str, Any]) -> dict[str, Any] | None:
    features = dict((record.get("feature_snapshot") or {}).get("feature_values") or {})
    if not features:
        return None
    outcome = dict(record.get("outcome_5d") or {})
    row = {
        "as_of": _as_of_key(record.get("as_of")),
        "symbol": record.get("symbol", ""),
        "strategy_key": record.get("strategy_key", ""),
        "market_state": (record.get("feature_snapshot") or {}).get("market_state", ""),
        "sell_now_better": _sell_now_better(record, outcome),
        "pullback_risk": _pullback_risk(outcome),
        "best_sell_ratio": _best_sell_ratio(record, outcome),
        "next_return_pct": float(outcome.get("return_5d_pct", 0.0) or 0.0),
        "hit_stop_loss_next": float(outcome.get("max_adverse_5d_pct", 0.0) or 0.0) <= -3.0,
    }
    for name in EXIT_MODEL_FEATURE_COLUMNS:
        row[name] = float(features.get(name, 0.0) or 0.0)
    return row


def _time_split(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    if not rows:
        return [], [], []
    train_end = max(1, int(len(rows) * 0.6))
    validation_end = max(train_end + 1, int(len(rows) * 0.8))
    return rows[:train_end], rows[train_end:validation_end], rows[validation_end:]


def _sell_now_better(record: dict[str, Any], outcome: dict[str, Any]) -> bool:
    model_action = str(record.get("model_action") or "")
    future_return = float(outcome.get("return_5d_pct", 0.0) or 0.0)
    return model_action.startswith("sell") and future_return <= 0


def _pullback_risk(outcome: dict[str, Any]) -> bool:
    return float(outcome.get("max_adverse_5d_pct", 0.0) or 0.0) <= -2.5


def _best_sell_ratio(record: dict[str, Any], outcome: dict[str, Any]) -> int:
    if _pullback_risk(outcome):
        return 70
    if _sell_now_better(record, outcome):
        return 50
    return 0


def _as_of_key(value: Any) -> str:
    try:
        return datetime.fromisoformat(str(value)).isoformat()
    except Exception:
        return str(value or "")
