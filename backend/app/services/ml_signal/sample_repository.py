from __future__ import annotations

from typing import Any

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import BacktestTrade, DailyBarSnapshot, Instrument, MLSignalSample, PaperTrade
from app.services.ml_signal.features import (
    empty_sequence_features,
    sequence_features_from_bars,
    trade_features,
)
from app.services.ml_signal.modeling import json_dumps


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
        if len(rows) < 11:
            return {
                "sector_relative_strength_5d": 0.0,
                "sector_relative_strength_10d": 0.0,
            }
        instrument = self.db.execute(select(Instrument).where(Instrument.symbol == symbol)).scalar_one_or_none()
        sector = str(instrument.sector_name or "").strip() if instrument is not None else ""
        if not sector:
            return {
                "sector_relative_strength_5d": 0.0,
                "sector_relative_strength_10d": 0.0,
            }
        peers = (
            self.db.execute(
                select(Instrument.symbol)
                .where(Instrument.sector_name == sector)
                .where(Instrument.instrument_type == "stock")
                .limit(120)
            )
            .scalars()
            .all()
        )
        peer_symbols = [item for item in peers if item and item != symbol]
        if not peer_symbols:
            return {
                "sector_relative_strength_5d": 0.0,
                "sector_relative_strength_10d": 0.0,
            }
        trade_dates = [str(row.trade_date) for row in rows[-11:]]
        peer_rows = (
            self.db.execute(
                select(DailyBarSnapshot)
                .where(DailyBarSnapshot.symbol.in_(peer_symbols))
                .where(DailyBarSnapshot.trade_date.in_(trade_dates))
            )
            .scalars()
            .all()
        )
        by_symbol: dict[str, dict[str, float]] = {}
        for row in peer_rows:
            if float(row.close_price or 0.0) <= 0:
                continue
            by_symbol.setdefault(str(row.symbol), {})[str(row.trade_date)] = float(row.close_price or 0.0)
        symbol_closes = {str(row.trade_date): float(row.close_price or 0.0) for row in rows if float(row.close_price or 0.0) > 0}

        def relative(days: int) -> float:
            if len(trade_dates) <= days:
                return 0.0
            start_date = trade_dates[-days - 1]
            end_date = trade_dates[-1]
            own_start = symbol_closes.get(start_date, 0.0)
            own_end = symbol_closes.get(end_date, 0.0)
            if own_start <= 0 or own_end <= 0:
                return 0.0
            own_momentum = (own_end / own_start - 1.0) * 100
            peer_momentum: list[float] = []
            for values in by_symbol.values():
                start = values.get(start_date, 0.0)
                end = values.get(end_date, 0.0)
                if start > 0 and end > 0:
                    peer_momentum.append((end / start - 1.0) * 100)
            if not peer_momentum:
                return 0.0
            return round(own_momentum - float(np.mean(peer_momentum)), 4)

        return {
            "sector_relative_strength_5d": relative(5),
            "sector_relative_strength_10d": relative(10),
        }
