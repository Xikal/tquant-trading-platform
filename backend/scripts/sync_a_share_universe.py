from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import delete, func, select

ROOT_DIR = Path(__file__).resolve().parents[2]
APP_DIR = ROOT_DIR / "backend"

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from app.core.database import SessionLocal, init_db
from app.models.entities import Instrument, LowBuyStrategyPoolSnapshot
from app.services.market_data import MarketDataService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="同步全 A 非 ST 股票基础信息和行业映射")
    parser.add_argument("--clear-strategy-pools", action="store_true", help="同步后清空策略样本池，下一次筛选自动重建")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    init_db()
    service = MarketDataService()
    with SessionLocal() as db:
        result = service.sync_instruments(db, "stock")
        removed = _delete_st_instruments(db)
        if args.clear_strategy_pools:
            db.execute(delete(LowBuyStrategyPoolSnapshot))
        db.commit()
        coverage = _coverage(db)
    print(
        {
            "synced": result,
            "removed_st_or_delist": removed,
            "coverage": coverage,
            "strategy_pools_cleared": bool(args.clear_strategy_pools),
        },
        flush=True,
    )
    return 0


def _delete_st_instruments(db) -> int:
    rows = db.execute(select(Instrument).where(Instrument.instrument_type == "stock")).scalars().all()
    removed = 0
    for row in rows:
        if _is_st_or_delist_name(row.name):
            db.delete(row)
            removed += 1
    return removed


def _coverage(db) -> dict[str, int]:
    total = int(
        db.execute(select(func.count(Instrument.id)).where(Instrument.instrument_type == "stock")).scalar_one()
        or 0
    )
    sector_filled = int(
        db.execute(
            select(func.count(Instrument.id)).where(
                Instrument.instrument_type == "stock",
                Instrument.sector_name.is_not(None),
                Instrument.sector_name != "",
            )
        ).scalar_one()
        or 0
    )
    return {"stock_total": total, "sector_filled": sector_filled}


def _is_st_or_delist_name(name: str) -> bool:
    upper_name = str(name or "").upper()
    return "ST" in upper_name or str(name or "").startswith("退市")


if __name__ == "__main__":
    raise SystemExit(main())
