#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from sqlalchemy import func, select  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.models.entities import DailyBarSnapshot, LowBuyStrategyPoolSnapshot, StrategyMetadata  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="探测龙头回踩波段策略样本可用性")
    parser.add_argument("--min-count", type=int, default=20, help="通过探针的最小候选数量")
    args = parser.parse_args()
    with SessionLocal() as db:
        latest = db.execute(select(func.max(DailyBarSnapshot.trade_date))).scalar()
        if not latest:
            _update_probe(db, "failed", "日线数据为空，无法验证龙头回踩波段样本。")
            print("failed: no daily bars")
            return
        count = int(
            db.execute(
                select(func.count(LowBuyStrategyPoolSnapshot.id)).where(
                    LowBuyStrategyPoolSnapshot.strategy_key == "leader_pullback_band",
                    LowBuyStrategyPoolSnapshot.latest_trade_date == str(latest),
                )
            ).scalar()
            or 0
        )
        status = "passed" if count >= args.min_count else "pending"
        summary = f"{latest} 龙头回踩波段候选 {count} 个，阈值 {args.min_count}。"
        _update_probe(db, status, summary)
        print(f"{status}: {summary}")


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


if __name__ == "__main__":
    main()
