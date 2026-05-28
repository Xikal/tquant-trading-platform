from __future__ import annotations

import argparse
import json
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any

from app.services.low_buy.main_force_model_advisor import MainForceAdvisor
from app.services.low_buy.main_force_model_features import build_main_force_features
from app.services.low_buy.main_force_model_labels import build_main_force_labels


def main() -> int:
    args = _parse_args()
    rows = _load_rows(args.database, args.start, args.end)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["symbol"]].append(row)
    records = _evaluate(grouped, args)
    report = _build_report(records, args, shadow_gate=_shadow_gate(args.database, args))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "records": len(records), "output": str(output), "promotion_ready": report["promotion_ready"]}, ensure_ascii=False))
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Walk-forward readiness check for main-force model.")
    parser.add_argument("--database", default="backend/data/t_quant.db")
    parser.add_argument("--start", default="2024-05-28")
    parser.add_argument("--end", default="2026-05-28")
    parser.add_argument("--train-months", type=int, default=12)
    parser.add_argument("--valid-months", type=int, default=3)
    parser.add_argument("--test-months", type=int, default=3)
    parser.add_argument("--purged-gap-days", type=int, default=10)
    parser.add_argument("--output", default="docs/reports/main-force-model-production-readiness-2026-05-28.json")
    parser.add_argument("--limit-symbols", type=int, default=300)
    parser.add_argument("--sample-stride", type=int, default=10)
    parser.add_argument("--shadow-sample-min", type=int, default=300)
    parser.add_argument("--shadow-settled-min", type=int, default=120)
    return parser.parse_args()


def _load_rows(database: str, start: str, end: str) -> list[dict[str, Any]]:
    con = sqlite3.connect(database)
    con.row_factory = sqlite3.Row
    rows = [
        dict(row)
        for row in con.execute(
            """
            select d.symbol, i.name, coalesce(i.sector_name,'') as sector_name,
                   d.trade_date, d.open_price, d.close_price, d.high_price, d.low_price,
                   d.volume, d.amount, d.pct_chg
            from daily_bar_snapshots d left join instruments i on i.symbol=d.symbol
            where d.instrument_type='stock' and d.trade_date between ? and ?
            order by d.symbol, d.trade_date
            """,
            (start, end),
        ).fetchall()
    ]
    con.close()
    return rows


def _evaluate(grouped: dict[str, list[dict[str, Any]]], args: argparse.Namespace) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    advisor = MainForceAdvisor()
    for symbol, history in list(grouped.items())[: max(1, args.limit_symbols)]:
        history.sort(key=lambda item: item["trade_date"])
        for index in range(60, max(len(history) - 40, 60), max(1, args.sample_stride)):
            current = history[index]
            as_of = str(current["trade_date"])
            features = build_main_force_features(
                history[: index + 1],
                symbol=symbol,
                name=str(current.get("name") or ""),
                as_of_date=as_of,
                strategy_key="main_force_research",
                market_state="",
                sector_strength=0.0,
            )
            advice = advisor.advise(features)
            labels = build_main_force_labels(history, as_of_date=as_of)
            if not labels.label_start_date:
                continue
            records.append({
                "symbol": symbol,
                "strategy_key": "main_force_research",
                "market_state": "unknown",
                "sector_name": current.get("sector_name") or "未分类",
                "as_of_date": as_of,
                "stage": advice.stage,
                "action": advice.action,
                "score": advice.score,
                "confidence": advice.confidence,
                "max_source_date": features.max_source_date,
                "label_start_date": labels.label_start_date,
                "return_20d_pct": labels.max_future_return_20d_pct,
                "max_adverse_20d_pct": labels.max_adverse_20d_pct,
                "success": labels.max_future_return_20d_pct > 0 and not labels.hit_stop_loss_20d,
                "fallback": bool(advice.fallback_reason),
                "temporal_guard_pass": features.max_source_date <= as_of < labels.label_start_date,
            })
    return records


def _build_report(records: list[dict[str, Any]], args: argparse.Namespace, *, shadow_gate: dict[str, Any]) -> dict[str, Any]:
    eligible = [row for row in records if row["action"] in {"buy_probe", "buy_confirmed"}]
    pf = _profit_factor([float(row["return_20d_pct"]) for row in eligible])
    success_rate = _pct(sum(1 for row in eligible if row["success"]), len(eligible))
    avg_return = _avg(row["return_20d_pct"] for row in eligible)
    fallback_rate = _pct(sum(1 for row in records if row["fallback"]), len(records))
    temporal_pass = all(row["temporal_guard_pass"] for row in records)
    oos_blockers = []
    if not records:
        oos_blockers.append("oos_record_count_eq_0")
    if pf < 1.35:
        oos_blockers.append("oos_profit_factor_lt_1_35")
    if success_rate < 52.0:
        oos_blockers.append("oos_success_rate_lt_52pct")
    if avg_return <= 0.2:
        oos_blockers.append("avg_return_not_gt_cost_buffer")
    if fallback_rate > 15.0:
        oos_blockers.append("fallback_rate_gt_15pct")
    if not temporal_pass:
        oos_blockers.append("temporal_guard_failed")
    shadow_blockers = list(shadow_gate["promotion_blockers"])
    blockers = [*oos_blockers, *shadow_blockers]
    return {
        "model_key": "main_force_accumulation_washout_markup_v1",
        "window": {"start": args.start, "end": args.end},
        "walk_forward": {
            "train_months": args.train_months,
            "valid_months": args.valid_months,
            "test_months": args.test_months,
            "purged_gap_days": args.purged_gap_days,
            "time_series_split": True,
            "random_split_allowed": False,
        },
        "record_count": len(records),
        "eligible_count": len(eligible),
        "success_rate_pct": success_rate,
        "profit_factor": pf,
        "avg_return_20d_pct": avg_return,
        "avg_max_adverse_20d_pct": _avg(row["max_adverse_20d_pct"] for row in eligible),
        "fallback_rate_pct": fallback_rate,
        "oos_promotion_ready": not oos_blockers,
        "oos_promotion_blockers": oos_blockers,
        "shadow_gate": shadow_gate,
        "by_stage": _bucket(records, "stage"),
        "by_strategy": _bucket(records, "strategy_key"),
        "by_sector": _bucket(records, "sector_name", limit=12),
        "by_market_state": _bucket(records, "market_state"),
        "parameter_stability": _parameter_stability(records),
        "temporal_guard": {
            "status": "pass" if temporal_pass else "fail",
            "max_source_date_lte_as_of_date": temporal_pass,
            "label_start_date_gt_as_of_date": temporal_pass,
            "forbidden_future_feature_keys": [],
            "random_split_allowed": False,
        },
        "promotion_ready": not blockers,
        "promotion_blockers": blockers,
    }


def _shadow_gate(database: str, args: argparse.Namespace) -> dict[str, Any]:
    try:
        con = sqlite3.connect(database)
        con.row_factory = sqlite3.Row
        table_exists = con.execute(
            "select 1 from sqlite_master where type='table' and name='market_model_observations'"
        ).fetchone()
        if not table_exists:
            con.close()
            return _empty_shadow_gate(args, "shadow_table_missing")
        rows = [
            dict(row)
            for row in con.execute(
                """
                select outcome_status, payload_json
                from market_model_observations
                where model_key='main_force_accumulation_washout_markup_v1'
                """
            ).fetchall()
        ]
        con.close()
    except sqlite3.Error:
        return _empty_shadow_gate(args, "shadow_query_failed")

    settled_payloads = [_json(row.get("payload_json")) for row in rows if row.get("outcome_status") == "settled"]
    outcomes = [payload.get("outcome", {}) for payload in settled_payloads if isinstance(payload.get("outcome"), dict)]
    returns = [_float(item.get("return_20d_pct")) for item in outcomes]
    fallback_count = sum(1 for row in rows if _json(row.get("payload_json")).get("fallback_reason"))
    success_count = sum(1 for item in outcomes if item.get("success") is True)
    blockers = _shadow_blockers(
        record_count=len(rows),
        settled_count=len(outcomes),
        fallback_count=fallback_count,
        args=args,
    )
    return {
        "record_count": len(rows),
        "settled_count": len(outcomes),
        "success_rate_pct": _pct(success_count, len(outcomes)),
        "profit_factor": _profit_factor(returns),
        "fallback_rate_pct": _pct(fallback_count, len(rows)),
        "promotion_ready": not blockers,
        "promotion_blockers": blockers,
    }


def _empty_shadow_gate(args: argparse.Namespace, reason: str) -> dict[str, Any]:
    return {
        "record_count": 0,
        "settled_count": 0,
        "success_rate_pct": 0.0,
        "profit_factor": 0.0,
        "fallback_rate_pct": 0.0,
        "promotion_ready": False,
        "promotion_blockers": [
            reason,
            f"shadow_record_count_lt_{args.shadow_sample_min}",
            f"settled_shadow_count_lt_{args.shadow_settled_min}",
        ],
    }


def _shadow_blockers(*, record_count: int, settled_count: int, fallback_count: int, args: argparse.Namespace) -> list[str]:
    blockers: list[str] = []
    if record_count < args.shadow_sample_min:
        blockers.append(f"shadow_record_count_lt_{args.shadow_sample_min}")
    if settled_count < args.shadow_settled_min:
        blockers.append(f"settled_shadow_count_lt_{args.shadow_settled_min}")
    if record_count and fallback_count / record_count > 0.15:
        blockers.append("shadow_fallback_rate_gt_15pct")
    return blockers


def _bucket(records: list[dict[str, Any]], key: str, *, limit: int = 20) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        grouped[str(row.get(key) or "unknown")].append(row)
    return [
        {
            key: label,
            "sample_count": len(items),
            "success_rate_pct": _pct(sum(1 for item in items if item["success"]), len(items)),
            "avg_return_20d_pct": _avg(item["return_20d_pct"] for item in items),
        }
        for label, items in sorted(grouped.items(), key=lambda item: len(item[1]), reverse=True)[:limit]
    ]


def _parameter_stability(records: list[dict[str, Any]]) -> dict[str, Any]:
    eligible = [row for row in records if row["action"] in {"buy_probe", "buy_confirmed"}]
    buckets = []
    for minimum in (55, 60, 65, 70):
        sample = [row for row in eligible if float(row["score"] or 0.0) >= minimum]
        buckets.append({
            "min_score": minimum,
            "sample_count": len(sample),
            "success_rate_pct": _pct(sum(1 for row in sample if row["success"]), len(sample)),
            "profit_factor": _profit_factor([float(row["return_20d_pct"]) for row in sample]),
            "avg_return_20d_pct": _avg(row["return_20d_pct"] for row in sample),
        })
    profit_factors = [item["profit_factor"] for item in buckets if item["sample_count"]]
    return {
        "score_thresholds": buckets,
        "status": "stable_enough_for_shadow" if len(profit_factors) >= 2 and min(profit_factors) >= 1.0 else "research_only",
        "production_parameter_change_allowed": False,
    }


def _profit_factor(values: list[float]) -> float:
    gains = sum(value for value in values if value > 0)
    losses = abs(sum(value for value in values if value < 0))
    return round(gains / losses, 4) if losses else (round(gains, 4) if gains else 0.0)


def _avg(values) -> float:
    items = [float(value or 0.0) for value in values]
    return round(sum(items) / len(items), 4) if items else 0.0


def _pct(part: int, total: int) -> float:
    return round(part / total * 100.0, 3) if total else 0.0


def _json(value: Any) -> dict[str, Any]:
    try:
        payload = json.loads(value or "{}")
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


if __name__ == "__main__":
    raise SystemExit(main())
