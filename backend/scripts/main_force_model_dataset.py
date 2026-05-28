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
    rows = _load_rows(args.database, limit_symbols=args.limit_symbols)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["symbol"]].append(row)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output.open("w", encoding="utf-8") as file:
        for symbol, history in grouped.items():
            history.sort(key=lambda item: item["trade_date"])
            for index in range(args.min_history, max(len(history) - args.label_window, args.min_history)):
                current = history[index]
                if index % args.sample_stride != 0:
                    continue
                if _mean_amount(history[index - 19 : index + 1]) < args.min_amount:
                    continue
                features = build_main_force_features(
                    history[: index + 1],
                    symbol=symbol,
                    name=str(current.get("name") or ""),
                    as_of_date=str(current["trade_date"]),
                    market_state="",
                    sector_strength=0.0,
                )
                advice = MainForceAdvisor().advise(features)
                labels = build_main_force_labels(history, as_of_date=str(current["trade_date"]), window_40=args.label_window)
                file.write(
                    json.dumps(
                        {
                            "features": features.to_dict(),
                            "advice": advice.to_dict(),
                            "labels": labels.to_dict(),
                            "temporal_guard": _temporal_guard(features.to_dict(), labels.to_dict()),
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                count += 1
                if args.max_samples and count >= args.max_samples:
                    print(json.dumps({"ok": True, "samples": count, "output": str(output)}, ensure_ascii=False))
                    return 0
    print(json.dumps({"ok": True, "samples": count, "output": str(output)}, ensure_ascii=False))
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build shadow dataset for main-force accumulation/washout/markup model.")
    parser.add_argument("--database", default="backend/data/t_quant.db")
    parser.add_argument("--output", default="docs/reports/main-force-model-dataset-sample.jsonl")
    parser.add_argument("--limit-symbols", type=int, default=200)
    parser.add_argument("--max-samples", type=int, default=5000)
    parser.add_argument("--min-history", type=int, default=60)
    parser.add_argument("--label-window", type=int, default=40)
    parser.add_argument("--sample-stride", type=int, default=5)
    parser.add_argument("--min-amount", type=float, default=50_000_000)
    return parser.parse_args()


def _load_rows(database: str, *, limit_symbols: int) -> list[dict[str, Any]]:
    con = sqlite3.connect(database)
    con.row_factory = sqlite3.Row
    symbols = [
        row["symbol"]
        for row in con.execute(
            """
            select d.symbol
            from daily_bar_snapshots d
            where d.instrument_type='stock' and coalesce(d.is_st,0)=0 and coalesce(d.is_delisted,0)=0
            group by d.symbol
            having count(*) >= 120 and avg(d.amount) >= 50000000
            order by avg(d.amount) desc
            limit ?
            """,
            (limit_symbols,),
        ).fetchall()
    ]
    if not symbols:
        con.close()
        return []
    placeholders = ",".join("?" for _ in symbols)
    rows = [
        dict(row)
        for row in con.execute(
            f"""
            select d.symbol, i.name, d.trade_date, d.open_price, d.close_price, d.high_price, d.low_price,
                   d.volume, d.amount, d.pct_chg
            from daily_bar_snapshots d left join instruments i on i.symbol=d.symbol
            where d.symbol in ({placeholders})
            order by d.symbol, d.trade_date
            """,
            symbols,
        ).fetchall()
    ]
    con.close()
    return rows


def _mean_amount(rows: list[dict[str, Any]]) -> float:
    values = [float(row.get("amount") or 0.0) for row in rows]
    return sum(values) / len(values) if values else 0.0


def _temporal_guard(features: dict[str, Any], labels: dict[str, Any]) -> dict[str, Any]:
    as_of = str(features.get("as_of_date") or labels.get("as_of_date") or "")
    max_source = str(features.get("max_source_date") or "")
    label_start = str(labels.get("label_start_date") or "")
    feature_values = features.get("feature_values") if isinstance(features.get("feature_values"), dict) else {}
    forbidden_keys = [key for key in feature_values if "future" in str(key).lower()]
    return {
        "max_source_date_lte_as_of_date": bool(max_source and as_of and max_source <= as_of),
        "label_start_date_gt_as_of_date": bool(label_start and as_of and label_start > as_of),
        "forbidden_future_feature_keys": forbidden_keys,
        "status": "pass" if max_source <= as_of < label_start and not forbidden_keys else "fail",
    }


if __name__ == "__main__":
    raise SystemExit(main())
