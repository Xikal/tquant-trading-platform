from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import BacktestTrade, DailyBarSnapshot, MLSignalSample, PaperTrade
from app.services.ml_signal.features import (
    empty_sequence_features,
    sequence_features_from_bars,
    trade_features,
)
from app.services.ml_signal.modeling import json_dumps
from app.services.ml_signal.sector_relative import sector_relative_strength_from_etf_proxy


class MLSignalSampleRepository:
    """Build and persist ML samples from paper trades, backtests and daily bars."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self._sequence_feature_cache: dict[tuple[str, str], dict[str, float]] = {}

    def paper_samples(self, limit: int) -> list[dict[str, Any]]:
        recent_rows = self.db.execute(
            select(PaperTrade).order_by(PaperTrade.id.desc()).limit(max(limit * 4, 500))
        ).scalars().all()
        rows = list(reversed(recent_rows))
        samples: list[dict[str, Any]] = []
        ledger: dict[tuple[int, str], dict[str, float]] = {}
        for row in rows:
            key = (int(row.account_id or 0), str(row.symbol or ""))
            quantity = int(row.quantity or 0)
            if quantity <= 0:
                continue
            if row.side == "buy":
                position = ledger.setdefault(key, {"quantity": 0.0, "cost": 0.0})
                position["quantity"] += quantity
                position["cost"] += float(row.net_amount or row.gross_amount or 0)
                continue
            if row.side != "sell":
                continue
            position = ledger.get(key)
            if not position or position["quantity"] <= 0:
                continue
            matched_quantity = min(quantity, int(position["quantity"]))
            if matched_quantity <= 0:
                continue
            avg_cost = position["cost"] / max(position["quantity"], 1.0)
            cost_basis = avg_cost
            fee_amount = float(row.commission or 0) + float(row.stamp_tax or 0) + float(row.transfer_fee or 0)
            pnl_amount = (float(row.price or 0) - cost_basis) * matched_quantity - fee_amount
            return_pct = (float(row.price or 0) / cost_basis - 1.0) * 100 if cost_basis > 0 else 0.0
            trade_date = row.trade_time.date().isoformat() if row.trade_time else ""
            samples.append(
                {
                    "sample_key": f"paper_close:{row.id}",
                    "symbol": row.symbol,
                    "trade_date": trade_date,
                    "strategy_key": row.strategy_key,
                    "source": "paper",
                    "features": trade_features(
                        price=float(row.price or 0),
                        quantity=matched_quantity,
                        gross_amount=float(row.gross_amount or 0),
                        strategy_key=row.strategy_key,
                        market_state=row.market_state,
                        side=row.side,
                        sequence_features=self.sequence_features(row.symbol, trade_date),
                    ),
                    "label": {
                        "closed": True,
                        "side": row.side,
                        "cost_basis": round(cost_basis, 6),
                        "pnl_amount": round(pnl_amount, 6),
                        "return_pct": round(return_pct, 6),
                        "pnl_pct": round(return_pct, 6),
                        "paper_trade_id": row.id,
                        "paper_order_id": row.order_id,
                        "account_id": row.account_id,
                        "exit_reason": row.exit_reason,
                    },
                }
            )
            position["quantity"] -= matched_quantity
            position["cost"] = max(position["quantity"], 0.0) * avg_cost
            if len(samples) >= limit:
                break
        return list(reversed(samples))

    def backtest_samples(self, limit: int) -> list[dict[str, Any]]:
        rows = self.db.execute(
            select(BacktestTrade).order_by(BacktestTrade.id.desc()).limit(limit)
        ).scalars().all()
        return [
            {
                "sample_key": f"backtest:{row.id}",
                "symbol": row.symbol,
                "trade_date": row.trade_date,
                "strategy_key": row.strategy_key,
                "source": "backtest",
                "features": trade_features(
                    price=float(row.price or 0),
                    quantity=int(row.quantity or 0),
                    gross_amount=float(row.gross_amount or 0),
                    strategy_key=row.strategy_key,
                    market_state=row.market_state,
                    side=row.side,
                    sequence_features=self.sequence_features(row.symbol, row.trade_date),
                ),
                "label": {"pnl_pct": float(row.pnl_pct or 0), "pnl_amount": float(row.pnl_amount or 0)},
            }
            for row in rows
        ]

    def persist_sample(self, sample: dict[str, Any]) -> bool:
        existing = self.db.execute(
            select(MLSignalSample).where(MLSignalSample.sample_key == sample["sample_key"])
        ).scalar_one_or_none()
        if existing is not None:
            return False
        self.db.add(
            MLSignalSample(
                sample_key=sample["sample_key"],
                symbol=sample["symbol"],
                trade_date=sample["trade_date"],
                strategy_key=sample["strategy_key"],
                source=sample["source"],
                feature_json=json_dumps(sample["features"]),
                label_json=json_dumps(sample["label"]),
            )
        )
        return True

    def sequence_features(self, symbol: str, trade_date: str) -> dict[str, float]:
        key = (str(symbol or ""), str(trade_date or ""))
        if not key[0] or not key[1]:
            return empty_sequence_features()
        cached = self._sequence_feature_cache.get(key)
        if cached is not None:
            return cached
        rows = (
            self.db.execute(
                select(DailyBarSnapshot)
                .where(DailyBarSnapshot.symbol == key[0])
                .where(DailyBarSnapshot.trade_date <= key[1])
                .order_by(DailyBarSnapshot.trade_date.desc())
                .limit(80)
            )
            .scalars()
            .all()
        )
        ordered_rows = list(reversed(rows))
        features = sequence_features_from_bars(ordered_rows)
        features.update(self.sector_relative_strength(key[0], ordered_rows))
        self._sequence_feature_cache[key] = features
        return features

    def sector_relative_strength(self, symbol: str, rows: list[DailyBarSnapshot]) -> dict[str, float]:
        return sector_relative_strength_from_etf_proxy(self.db, symbol=symbol, rows=rows)
