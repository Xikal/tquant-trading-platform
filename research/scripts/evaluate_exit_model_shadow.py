from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.database import SessionLocal, init_db
from app.services.paper.exit_model_dataset import build_exit_model_dataset, synthetic_exit_model_records
from app.services.paper.exit_model_shadow import latest_exit_model_shadow_records, summarize_exit_model_shadow


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate paper exit model Shadow outcomes")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--model", default="")
    parser.add_argument("--output", default="")
    parser.add_argument("--limit", type=int, default=5000)
    parser.add_argument("--lookback-days", type=int, default=60)
    args = parser.parse_args()
    if args.smoke:
        records = synthetic_exit_model_records()
        summary = _summary_from_records(records)
    else:
        init_db()
        with SessionLocal() as db:
            records = latest_exit_model_shadow_records(db, limit=args.limit)
            summary = {
                **summarize_exit_model_shadow(db, lookback_days=args.lookback_days),
                **_summary_from_records(records),
            }
    report = {
        "version": "exit-model-shadow-evaluation-v1",
        "model_path": str(Path(args.model).expanduser()) if args.model else "",
        "smoke": bool(args.smoke),
        "record_count": len(records),
        "summary": summary,
        "groups": _group_reports(records),
        "dataset": build_exit_model_dataset(records).metadata,
    }
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def _summary_from_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    if not records:
        return {
            "fallback_count": 0,
            "fallback_rate_pct": 0.0,
            "hard_stop_shadow_count": 0,
            "sell_flying_count": 0,
            "sell_flying_rate_pct": 0.0,
            "avg_pullback_5d_pct": 0.0,
            "avg_return_5d_pct": 0.0,
            "stop_loss_execution_rate_pct": 0.0,
        }
    fallback_count = sum(1 for item in records if item.get("fallback_reason"))
    hard_stop_count = sum(1 for item in records if item.get("rule_action") == "hard_stop")
    sell_records = [item for item in records if str(item.get("model_action", "")).startswith("sell")]
    sell_flying = [
        item for item in sell_records
        if _outcome_float(item, "max_favorable_5d_pct") >= 5.0
    ]
    stop_loss_records = [item for item in records if item.get("rule_action") == "hard_stop"]
    return {
        "fallback_count": fallback_count,
        "fallback_rate_pct": _pct(fallback_count, len(records)),
        "hard_stop_shadow_count": hard_stop_count,
        "sell_flying_count": len(sell_flying),
        "sell_flying_rate_pct": _pct(len(sell_flying), len(sell_records)),
        "avg_pullback_5d_pct": _avg(_outcome_float(item, "max_adverse_5d_pct") for item in records),
        "avg_return_5d_pct": _avg(_outcome_float(item, "return_5d_pct") for item in records),
        "stop_loss_execution_rate_pct": _pct(
            sum(1 for item in stop_loss_records if item.get("rule_action") == "hard_stop"),
            len(stop_loss_records),
        ),
    }


def _group_reports(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in records:
        key = str(item.get("strategy_key") or "unknown")
        grouped.setdefault(key, []).append(item)
    return {
        key: {
            "sample_count": len(items),
            "fallback_rate_pct": _pct(sum(1 for item in items if item.get("fallback_reason")), len(items)),
            "avg_return_5d_pct": _avg(_outcome_float(item, "return_5d_pct") for item in items),
            "avg_pullback_5d_pct": _avg(_outcome_float(item, "max_adverse_5d_pct") for item in items),
            "sell_flying_rate_pct": _pct(
                sum(1 for item in items if str(item.get("model_action", "")).startswith("sell") and _outcome_float(item, "max_favorable_5d_pct") >= 5.0),
                sum(1 for item in items if str(item.get("model_action", "")).startswith("sell")),
            ),
        }
        for key, items in sorted(grouped.items())
    }


def _outcome_float(record: dict[str, Any], key: str) -> float:
    outcome = record.get("outcome_5d")
    if not isinstance(outcome, dict):
        outcome = record.get("outcome")
    if not isinstance(outcome, dict):
        outcome = {}
    try:
        return float(outcome.get(key, 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _avg(values) -> float:
    items = [float(value or 0.0) for value in values]
    return round(sum(items) / len(items), 4) if items else 0.0


def _pct(part: int, total: int) -> float:
    return round(part / total * 100.0, 3) if total else 0.0


if __name__ == "__main__":
    raise SystemExit(main())
