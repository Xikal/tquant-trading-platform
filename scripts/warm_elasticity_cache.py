#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from sqlalchemy import func, select  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.models.entities import DailyBarSnapshot, LowBuyResultSnapshot, TradingElasticityCache, UserWatchlist, Watchlist  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="预热做T弹性缓存")
    parser.add_argument("--limit", type=int, default=200, help="最多预热标的数")
    args = parser.parse_args()
    with SessionLocal() as db:
        symbols = _collect_symbols(db, limit=max(1, args.limit))
        updated = 0
        for symbol in symbols:
            score, sample_count, payload = _compute_elasticity(db, symbol)
            row = db.execute(select(TradingElasticityCache).where(TradingElasticityCache.symbol == symbol)).scalar_one_or_none()
            if row is None:
                row = TradingElasticityCache(symbol=symbol)
                db.add(row)
            row.elasticity_score = score
            row.elasticity_tier = _tier(score, sample_count)
            row.data_quality = "ok" if sample_count >= 20 else "thin_sample"
            row.sample_count = sample_count
            row.payload_json = json.dumps(payload, ensure_ascii=False)
            row.computed_at = datetime.now()
            updated += 1
        db.commit()
    print(f"elasticity cache warmed: {updated}/{len(symbols)}")


def _collect_symbols(db, *, limit: int) -> list[str]:
    symbols: list[str] = []
    latest_date = db.execute(select(func.max(LowBuyResultSnapshot.latest_trade_date))).scalar()
    if latest_date:
        symbols.extend(
            str(value)
            for value in db.execute(
                select(LowBuyResultSnapshot.symbol)
                .where(LowBuyResultSnapshot.latest_trade_date == latest_date)
                .order_by(LowBuyResultSnapshot.score.desc())
                .limit(limit)
            ).scalars()
        )
    symbols.extend(str(value) for value in db.execute(select(Watchlist.symbol).limit(limit)).scalars())
    symbols.extend(str(value) for value in db.execute(select(UserWatchlist.symbol).limit(limit)).scalars())
    deduped: list[str] = []
    seen: set[str] = set()
    for symbol in symbols:
        if symbol and symbol not in seen:
            deduped.append(symbol)
            seen.add(symbol)
        if len(deduped) >= limit:
            break
    return deduped


def _compute_elasticity(db, symbol: str) -> tuple[float, int, dict]:
    rows = (
        db.execute(
            select(
                DailyBarSnapshot.trade_date,
                DailyBarSnapshot.open_price,
                DailyBarSnapshot.high_price,
                DailyBarSnapshot.low_price,
                DailyBarSnapshot.close_price,
                DailyBarSnapshot.amount,
            )
            .where(DailyBarSnapshot.symbol == symbol)
            .order_by(DailyBarSnapshot.trade_date.desc())
            .limit(60)
        )
        .all()
    )
    if len(rows) < 10:
        return 0.0, len(rows), {"reason": "sample_too_small"}
    amplitudes: list[float] = []
    intraday_pop: list[float] = []
    for _, open_price, high_price, low_price, close_price, amount in rows:
        open_v = float(open_price or 0)
        high_v = float(high_price or 0)
        low_v = float(low_price or 0)
        close_v = float(close_price or 0)
        if min(open_v, high_v, low_v, close_v) <= 0:
            continue
        amplitudes.append((high_v - low_v) / close_v * 100)
        intraday_pop.append((high_v - open_v) / open_v * 100)
    sample_count = len(amplitudes)
    if sample_count <= 0:
        return 0.0, 0, {"reason": "no_valid_bar"}
    avg_amp = sum(amplitudes) / sample_count
    avg_pop = sum(intraday_pop) / max(len(intraday_pop), 1)
    hit3 = sum(1 for value in intraday_pop if value >= 3.0) / max(len(intraday_pop), 1) * 100
    score = min(100.0, max(0.0, avg_amp * 8 + avg_pop * 10 + hit3 * 0.45))
    payload = {"avg_amplitude_pct": round(avg_amp, 2), "avg_intraday_pop_pct": round(avg_pop, 2), "hit3_pct": round(hit3, 2)}
    return round(score, 2), sample_count, payload


def _tier(score: float, sample_count: int) -> str:
    if sample_count < 20:
        return "unknown"
    if score >= 75:
        return "high"
    if score >= 50:
        return "medium"
    return "low"


if __name__ == "__main__":
    main()
