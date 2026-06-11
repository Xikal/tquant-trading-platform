from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

ROOT_DIR = Path(__file__).resolve().parents[2]
APP_DIR = ROOT_DIR / "backend"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from app.core.database import SessionLocal, init_db
from app.models.entities import MinuteBarSnapshot, TickTradeSnapshot
from app.services.low_buy.tradability_validation import (
    MinuteExecutionBar,
    TickTrade,
    candidate_from_outcome_row,
    replay_candidate_tradability,
)
from app.services.market.minute_bar_store import MinuteBarSnapshotStore
from app.services.market.tick_trade_store import TickTradeSnapshotStore


def _default_input_report(filename: str) -> Path:
    artifact_path = ROOT_DIR / "backend" / "data" / "reports" / filename
    if artifact_path.exists():
        return artifact_path
    return ROOT_DIR / "docs" / "reports" / filename


DEFAULT_SOURCE_REPORT = _default_input_report("front-row-weighted-production-scoring-backtest-2026-05-29.json")
DEFAULT_JSON_OUTPUT = ROOT_DIR / "backend" / "data" / "reports" / "front-row-weighted-minute-tick-tradability-2026-05-30.json"
DEFAULT_MD_OUTPUT = ROOT_DIR / "docs" / "reports" / "front-row-weighted-minute-tick-tradability-2026-05-30.md"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Front-row weighted minute/tick tradability validation")
    parser.add_argument("--source-report", default=str(DEFAULT_SOURCE_REPORT))
    parser.add_argument("--bar-period", default="1m")
    parser.add_argument("--json-output", default=str(DEFAULT_JSON_OUTPUT))
    parser.add_argument("--markdown-output", default=str(DEFAULT_MD_OUTPUT))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    source = _load_report(args.source_report)
    rows = source.get("variants", {}).get("front_row_weighted_max5", {}).get("outcome_rows", [])
    filled_rows = [row for row in rows if row.get("execution_status") == "filled"]
    init_db()
    with SessionLocal() as db:
        coverage = _coverage(db, filled_rows, bar_period=args.bar_period)
        replay = _replay_rows(db, filled_rows, bar_period=args.bar_period)
        tick_count = int(db.execute(select(func.count(TickTradeSnapshot.id))).scalar_one() or 0)
    minute_coverage_pct = float(coverage.get("coverage_pct") or 0.0)
    fill_retention_pct = round(replay["filled_count"] / max(len(filled_rows), 1) * 100.0, 4)
    blockers: list[str] = []
    if minute_coverage_pct < 95.0:
        blockers.append("minute_coverage_below_95pct")
    if tick_count <= 0:
        blockers.append("tick_data_insufficient_for_real_money_production")
    if fill_retention_pct < 70.0:
        blockers.append("tradability_fill_retention_below_70pct")
    report = {
        "title": "前排加权分钟级/逐笔级可成交性验证",
        "source_report": args.source_report,
        "bar_period": args.bar_period,
        "production_sort_replaced": False,
        "daily_bar_filled_count": len(filled_rows),
        "minute_coverage": coverage,
        "tick_coverage": {
            "tick_rows": tick_count,
            "status": "tick_available" if tick_count > 0 else "tick_data_insufficient",
        },
        "replay": replay,
        "fill_retention_pct": fill_retention_pct,
        "status": "passed" if not blockers else ("minute_pass_tick_blocked" if blockers == ["tick_data_insufficient_for_real_money_production"] else "blocked"),
        "blockers": blockers,
        "warnings": ["quote_estimate_depth_cannot_pass_real_money_gate"] if tick_count <= 0 else [],
    }
    _write_outputs(report, args.json_output, args.markdown_output)
    print(json.dumps({"json": args.json_output, "markdown": args.markdown_output, "status": report["status"], "blockers": blockers}, ensure_ascii=False, indent=2))
    return 0


def _coverage(db, rows: list[dict[str, Any]], *, bar_period: str) -> dict[str, Any]:
    symbols = sorted({str(row.get("symbol") or "") for row in rows if row.get("symbol")})
    dates = sorted({str(row.get("entry_trade_date") or "") for row in rows if row.get("entry_trade_date")})
    if not symbols or not dates:
        return {"coverage_pct": 0.0, "symbol_count": len(symbols), "covered_symbol_count": 0, "rows": 0, "missing_symbols": symbols}
    store = MinuteBarSnapshotStore(db)
    return store.coverage_summary(
        symbols=symbols,
        start=date.fromisoformat(dates[0]),
        end=date.fromisoformat(dates[-1]),
        bar_period=bar_period,
    )


def _replay_rows(db, rows: list[dict[str, Any]], *, bar_period: str) -> dict[str, Any]:
    minute_store = MinuteBarSnapshotStore(db)
    tick_store = TickTradeSnapshotStore(db)
    status_counts: dict[str, int] = {}
    reason_counts: dict[str, int] = {}
    samples: list[dict[str, Any]] = []
    for row in rows:
        entry_date = str(row.get("entry_trade_date") or "")
        if not entry_date:
            result = {"tradability_status": "data_missing", "reason": "entry_trade_date_missing"}
        else:
            candidate = candidate_from_outcome_row(row)
            bars = [
                _minute_bar_from_row(item)
                for item in minute_store.list_bars(symbol=candidate.symbol, trade_date=date.fromisoformat(entry_date), bar_period=bar_period, limit=300)
            ]
            ticks = [
                _tick_from_row(item)
                for item in tick_store.list_ticks(symbol=candidate.symbol, trade_date=date.fromisoformat(entry_date), limit=10000)
            ]
            result = replay_candidate_tradability(candidate, minute_bars=bars, tick_trades=ticks).as_dict()
        status = str(result.get("tradability_status") or "unknown")
        reason = str(result.get("reason") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
        if len(samples) < 50:
            samples.append({"symbol": row.get("symbol"), "signal_date": row.get("signal_date"), **result})
    return {
        "candidate_count": len(rows),
        "filled_count": int(status_counts.get("filled", 0)),
        "status_counts": dict(sorted(status_counts.items(), key=lambda item: (-item[1], item[0]))),
        "reason_counts": dict(sorted(reason_counts.items(), key=lambda item: (-item[1], item[0]))),
        "samples": samples,
    }


def _minute_bar_from_row(row: MinuteBarSnapshot) -> MinuteExecutionBar:
    return MinuteExecutionBar(
        trade_date=str(row.trade_date or ""),
        bar_timestamp=str(row.bar_timestamp or ""),
        open_price=float(row.open_price or 0.0),
        high_price=float(row.high_price or 0.0),
        low_price=float(row.low_price or 0.0),
        close_price=float(row.close_price or 0.0),
        volume=float(row.volume or 0.0),
        amount=float(row.amount or 0.0),
        pct_chg=float(row.change_pct or 0.0),
        data_quality=str(row.data_quality or "unknown"),
    )


def _tick_from_row(row: TickTradeSnapshot) -> TickTrade:
    return TickTrade(
        trade_date=str(row.trade_date or ""),
        trade_timestamp=str(row.trade_timestamp or ""),
        price=float(row.price or 0.0),
        volume=float(row.volume or 0.0),
        amount=float(row.amount or 0.0),
        side=str(row.side or ""),
        data_quality=str(row.data_quality or "unknown"),
    )


def _load_report(path: str) -> dict[str, Any]:
    report_path = Path(path)
    if not report_path.is_absolute():
        report_path = ROOT_DIR / report_path
    return json.loads(report_path.read_text(encoding="utf-8"))


def _write_outputs(report: dict[str, Any], json_output: str, markdown_output: str) -> None:
    json_path = Path(json_output)
    md_path = Path(markdown_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# 前排加权分钟级/逐笔级可成交性验证",
        "",
        f"- 状态：`{report['status']}`。",
        f"- 日线成交候选：{report['daily_bar_filled_count']}。",
        f"- 分钟线覆盖：{report['minute_coverage'].get('coverage_pct', 0.0):.2f}%。",
        f"- 逐笔数据行数：{report['tick_coverage'].get('tick_rows', 0)}。",
        f"- 可成交回放留存：{report['fill_retention_pct']:.2f}%。",
        "- 本报告只用于 Shadow/Paper；tick 数据不足时不得进入真实交易生产。",
        "",
        "## 阻断项",
        "",
    ]
    lines.extend([f"- `{item}`" for item in report["blockers"]] or ["- 无"])
    lines.extend([
        "",
        "## 回放统计",
        "",
        "| 指标 | 数值 |",
        "|---|---:|",
        f"| 候选数 | {report['replay']['candidate_count']} |",
        f"| 可成交数 | {report['replay']['filled_count']} |",
    ])
    for reason, count in report["replay"]["reason_counts"].items():
        lines.append(f"| {reason} | {count} |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
