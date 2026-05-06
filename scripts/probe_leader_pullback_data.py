#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from sqlalchemy import distinct, func, select  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.models.entities import (  # noqa: E402
    DailyBarSnapshot,
    IntradayConfirmationSnapshot,
    LowBuyResultSnapshot,
    LowBuyStrategyPoolSnapshot,
    StrategyMetadata,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="探测龙头回踩波段策略样本可用性")
    parser.add_argument("--min-count", type=int, default=20, help="通过探针的最小候选数量")
    parser.add_argument("--min-daily-count", type=int, default=4500, help="通过探针的最小日线股票覆盖")
    parser.add_argument("--output", default="", help="JSON 报告输出路径")
    parser.add_argument("--dry-run", action="store_true", help="只输出报告，不更新 strategy_metadata")
    args = parser.parse_args()
    try:
        with SessionLocal() as db:
            latest = db.execute(select(func.max(DailyBarSnapshot.trade_date))).scalar()
            if not latest:
                report = _report("failed", "日线数据为空，无法验证龙头回踩波段样本。")
                _emit_report(report, args.output)
                if not args.dry_run:
                    _update_probe(db, report["status"], report["summary"])
                return
            report = _build_probe_report(db, latest=str(latest), min_count=args.min_count, min_daily_count=args.min_daily_count)
            _emit_report(report, args.output)
            if not args.dry_run:
                _update_probe(db, report["status"], report["summary"])
    except Exception as exc:
        report = _report("failed", f"数据库不可用，无法验证龙头回踩波段样本：{type(exc).__name__}")
        _emit_report(report, args.output)
        raise SystemExit(2) from exc


def _update_probe(db, status: str, summary: str) -> None:
    row = db.execute(select(StrategyMetadata).where(StrategyMetadata.key == "leader_pullback_band")).scalar_one_or_none()
    if row is None:
        row = StrategyMetadata(
            key="leader_pullback_band",
            display_name="龙头回踩波段",
            description="热点龙头确认后回踩均线支撑的二波研究策略。",
            category="research",
            risk_level="high",
            typical_holding_days="3-10天",
            sort_order=70,
        )
        db.add(row)
    row.probe_status = status
    row.probe_summary = summary
    row.visibility = "backtest_only" if status != "passed" else "full"
    db.commit()


def _build_probe_report(db, *, latest: str, min_count: int, min_daily_count: int) -> dict:
    pool_count = _count_pool(db, latest)
    daily_count = int(
        db.execute(
            select(func.count(distinct(DailyBarSnapshot.symbol))).where(
                DailyBarSnapshot.trade_date == latest,
                DailyBarSnapshot.instrument_type == "stock",
            )
        ).scalar()
        or 0
    )
    industry_count = int(
        db.execute(
            select(func.count(distinct(LowBuyStrategyPoolSnapshot.industry))).where(
                LowBuyStrategyPoolSnapshot.strategy_key == "leader_pullback_band",
                LowBuyStrategyPoolSnapshot.latest_trade_date == latest,
                LowBuyStrategyPoolSnapshot.industry != "",
            )
        ).scalar()
        or 0
    )
    result_count = int(
        db.execute(
            select(func.count(LowBuyResultSnapshot.id)).where(
                LowBuyResultSnapshot.strategy_key == "leader_pullback_band",
                LowBuyResultSnapshot.latest_trade_date == latest,
            )
        ).scalar()
        or 0
    )
    intraday_count = int(
        db.execute(
            select(func.count(distinct(IntradayConfirmationSnapshot.symbol))).where(
                IntradayConfirmationSnapshot.trade_date == latest,
            )
        ).scalar()
        or 0
    )
    monthly = _monthly_pool_counts(db)
    dimensions = {
        "daily_market_coverage": {
            "value": daily_count,
            "threshold": min_daily_count,
            "passed": daily_count >= min_daily_count,
        },
        "strategy_pool_coverage": {
            "value": pool_count,
            "threshold": min_count,
            "passed": pool_count >= min_count,
        },
        "industry_breadth": {
            "value": industry_count,
            "threshold": 3,
            "passed": industry_count >= 3,
        },
        "intraday_or_result_coverage": {
            "value": max(intraday_count, result_count),
            "threshold": 1,
            "passed": max(intraday_count, result_count) >= 1,
        },
    }
    failed = [key for key, item in dimensions.items() if not item["passed"]]
    status = "passed" if not failed else "pending"
    if daily_count <= 0:
        status = "failed"
    summary = (
        f"{latest} 龙头回踩波段候选 {pool_count} 个，日线覆盖 {daily_count}，"
        f"行业覆盖 {industry_count}，盘中/结果覆盖 {max(intraday_count, result_count)}。"
    )
    return {
        "strategy_key": "leader_pullback_band",
        "latest_trade_date": latest,
        "status": status,
        "summary": summary,
        "dimensions": dimensions,
        "failed_dimensions": failed,
        "monthly_pool_counts": monthly,
    }


def _count_pool(db, latest: str) -> int:
    return int(
        db.execute(
            select(func.count(LowBuyStrategyPoolSnapshot.id)).where(
                LowBuyStrategyPoolSnapshot.strategy_key == "leader_pullback_band",
                LowBuyStrategyPoolSnapshot.latest_trade_date == latest,
            )
        ).scalar()
        or 0
    )


def _monthly_pool_counts(db) -> list[dict[str, object]]:
    rows = db.execute(
        select(
            func.substr(LowBuyStrategyPoolSnapshot.latest_trade_date, 1, 7).label("month"),
            func.count(LowBuyStrategyPoolSnapshot.id),
        )
        .where(LowBuyStrategyPoolSnapshot.strategy_key == "leader_pullback_band")
        .group_by("month")
        .order_by("month")
    ).all()
    return [{"month": str(month), "count": int(count or 0)} for month, count in rows if month]


def _report(status: str, summary: str) -> dict:
    return {
        "strategy_key": "leader_pullback_band",
        "latest_trade_date": "",
        "status": status,
        "summary": summary,
        "dimensions": {},
        "failed_dimensions": [],
        "monthly_pool_counts": [],
    }


def _emit_report(report: dict, output: str) -> None:
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if output:
        Path(output).write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
